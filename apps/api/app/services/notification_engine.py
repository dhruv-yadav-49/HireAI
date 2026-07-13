import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import CommunicationStatus, DeliveryEvent
from app.models.communication import Communication
from app.models.communication_delivery import CommunicationDelivery
from app.services.communication_dispatcher import CommunicationDispatcher

logger = logging.getLogger(__name__)


class NotificationEngine:
    """Core background runner engine for dispatching, retrying, and handling communication queues."""

    # Retry backoff delays: Attempt 1 (5s), Attempt 2 (30s), Attempt 3 (120s), Attempt 4 (600s)
    RETRY_BACKOFFS = [5, 30, 120, 600]

    @staticmethod
    async def send_queued_notifications(
        db: AsyncSession, organization_id: Optional[uuid.UUID] = None
    ) -> dict[str, int]:
        """Polls queued communication messages and dispatches them with retry-backoff protections."""
        now = datetime.now(timezone.utc)
        metrics = {"notifications_sent": 0, "notifications_failed": 0}

        stmt = select(Communication).where(
            Communication.status == CommunicationStatus.QUEUED,
            Communication.scheduled_at <= now,
        )
        if organization_id:
            stmt = stmt.where(Communication.organization_id == organization_id)

        res = await db.execute(stmt)
        queued_items = res.scalars().all()

        for item in queued_items:
            try:
                # Dispatch communication
                await CommunicationDispatcher.dispatch(db, item)
                metrics["notifications_sent"] += 1
            except Exception as exc:
                # Retrieve count of failed delivery events to determine current attempt number
                failed_count_stmt = select(func.count(CommunicationDelivery.id)).where(
                    CommunicationDelivery.communication_id == item.id,
                    CommunicationDelivery.event == DeliveryEvent.FAILED
                )
                failed_res = await db.execute(failed_count_stmt)
                failed_attempts = failed_res.scalar() or 0

                # Max attempts threshold is 4
                if failed_attempts >= len(NotificationEngine.RETRY_BACKOFFS):
                    item.status = CommunicationStatus.FAILED
                    db.add(item)
                    metrics["notifications_failed"] += 1
                    logger.error(
                        f"Communication {item.id} permanently failed after {failed_attempts} retry attempts."
                    )
                else:
                    # Reschedule retry for the future using backoff delays
                    delay = NotificationEngine.RETRY_BACKOFFS[failed_attempts - 1]
                    item.scheduled_at = now + timedelta(seconds=delay)
                    db.add(item)
                    logger.warning(
                        f"Communication {item.id} failed attempt {failed_attempts}. Retrying in {delay} seconds. Error: {exc}"
                    )

        await db.commit()
        return metrics

