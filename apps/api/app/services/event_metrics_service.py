from __future__ import annotations

import logging
from datetime import datetime, timezone
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_event import AIEvent
from app.models.ai_event_delivery import AIEventDelivery
from app.models.enums import EventType, EventStatus

logger = logging.getLogger(__name__)


class EventMetricsService:
    """Collects and surfaces operational metrics for the event bus.

    ADR-020: Operational Metrics (CTO refinement #14).
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def summary(self) -> dict:
        """Returns a health dashboard dict for the event bus.

        Covers:
        - Total events published
        - Breakdown by EventStatus
        - Delivery success rate
        - Dead-letter count
        - Pending / retrying delivery counts
        - Events published in the last 24 hours
        """
        # Total events
        total_events_stmt = select(func.count(AIEvent.id)).where(AIEvent.archived == False)
        total_events_result = await self.db.execute(total_events_stmt)
        total_events: int = total_events_result.scalar_one() or 0

        # Events published in last 24 hours
        from datetime import timedelta
        since_24h = datetime.now(timezone.utc) - timedelta(hours=24)
        recent_stmt = select(func.count(AIEvent.id)).where(
            AIEvent.published_at >= since_24h,
            AIEvent.archived == False,
        )
        recent_result = await self.db.execute(recent_stmt)
        recent_count: int = recent_result.scalar_one() or 0

        # Events by status
        event_status_stmt = (
            select(AIEvent.status, func.count(AIEvent.id))
            .where(AIEvent.archived == False)
            .group_by(AIEvent.status)
        )
        event_status_result = await self.db.execute(event_status_stmt)
        events_by_status: dict[str, int] = {
            str(row[0]): row[1] for row in event_status_result.all()
        }

        # Delivery counts by status
        delivery_status_stmt = (
            select(AIEventDelivery.status, func.count(AIEventDelivery.id))
            .group_by(AIEventDelivery.status)
        )
        delivery_status_result = await self.db.execute(delivery_status_stmt)
        deliveries_by_status: dict[str, int] = {
            str(row[0]): row[1] for row in delivery_status_result.all()
        }

        total_deliveries = sum(deliveries_by_status.values())
        delivered = deliveries_by_status.get(EventStatus.DELIVERED.value, 0)
        dead_letter = deliveries_by_status.get(EventStatus.DEAD_LETTER.value, 0)
        pending = deliveries_by_status.get(EventStatus.PENDING.value, 0)
        retrying = deliveries_by_status.get(EventStatus.RETRYING.value, 0)

        success_rate = round((delivered / total_deliveries * 100), 2) if total_deliveries else 0.0

        # Events per type (top 10)
        type_stmt = (
            select(AIEvent.event_type, func.count(AIEvent.id))
            .where(AIEvent.archived == False)
            .group_by(AIEvent.event_type)
            .order_by(func.count(AIEvent.id).desc())
            .limit(10)
        )
        type_result = await self.db.execute(type_stmt)
        events_by_type: dict[str, int] = {
            str(row[0]): row[1] for row in type_result.all()
        }

        return {
            "total_events_published": total_events,
            "events_last_24h": recent_count,
            "events_by_status": events_by_status,
            "events_by_type": events_by_type,
            "total_deliveries": total_deliveries,
            "deliveries_by_status": deliveries_by_status,
            "delivery_success_rate_pct": success_rate,
            "dead_letter_count": dead_letter,
            "pending_count": pending,
            "retrying_count": retrying,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def subscriber_summary(self) -> list[dict]:
        """Returns per-subscriber delivery success and failure counts."""
        from app.models.ai_event_subscription import AIEventSubscription
        from sqlalchemy.orm import aliased

        sub = aliased(AIEventSubscription)
        stmt = (
            select(
                sub.subscriber_name,
                sub.event_type,
                AIEventDelivery.status,
                func.count(AIEventDelivery.id).label("count"),
            )
            .join(sub, AIEventDelivery.subscriber_id == sub.id)
            .group_by(sub.subscriber_name, sub.event_type, AIEventDelivery.status)
            .order_by(sub.subscriber_name, AIEventDelivery.status)
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        # Aggregate into a clean list
        aggregated: dict[str, dict] = {}
        for subscriber_name, event_type, status, count in rows:
            key = f"{subscriber_name}::{event_type}"
            if key not in aggregated:
                aggregated[key] = {
                    "subscriber": subscriber_name,
                    "event_type": str(event_type),
                    "delivered": 0,
                    "failed": 0,
                    "retrying": 0,
                    "dead_letter": 0,
                    "pending": 0,
                }
            status_str = str(status).split(".")[-1].lower()  # normalize enum
            if status_str in aggregated[key]:
                aggregated[key][status_str] = count

        return list(aggregated.values())
