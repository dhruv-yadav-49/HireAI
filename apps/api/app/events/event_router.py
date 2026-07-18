from __future__ import annotations

import uuid
import logging
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_event import AIEvent
from app.models.ai_event_subscription import AIEventSubscription
from app.models.ai_event_delivery import AIEventDelivery
from app.models.enums import EventType, EventStatus

logger = logging.getLogger(__name__)


class EventRouter:
    """Routes an event to all matching enabled subscriptions, creating
    one AIEventDelivery row per subscriber pair.

    ADR-020: Subscriber Isolation — a subscriber failure never affects
    other subscribers for the same event (CTO refinement #6).
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_subscriptions(
        self, event_type: EventType
    ) -> list[AIEventSubscription]:
        """Returns all enabled subscriptions registered for the given event type."""
        stmt = select(AIEventSubscription).where(
            AIEventSubscription.event_type == event_type,
            AIEventSubscription.enabled == True,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def route(self, event: AIEvent) -> list[AIEventDelivery]:
        """Creates an AIEventDelivery record for every active subscriber
        that is registered for this event type.

        Returns the list of created delivery records.
        """
        subscriptions = await self.get_active_subscriptions(event.event_type)
        if not subscriptions:
            logger.debug(
                "EventRouter.route: no active subscriptions for event_type=%s",
                event.event_type.value,
            )
            return []

        deliveries: list[AIEventDelivery] = []
        for sub in subscriptions:
            # Idempotency guard: skip if a delivery record already exists
            existing = await self._get_existing_delivery(event.id, sub.id)
            if existing:
                logger.debug(
                    "EventRouter.route: delivery already exists for event=%s sub=%s, skipping",
                    event.id, sub.id,
                )
                deliveries.append(existing)
                continue

            delivery = AIEventDelivery(
                id=uuid.uuid4(),
                event_id=event.id,
                subscriber_id=sub.id,
                status=EventStatus.PENDING,
                attempt=0,
                processed_event_key=event.event_key,  # Idempotency tracking (CTO #5)
            )
            self.db.add(delivery)
            deliveries.append(delivery)

        if deliveries:
            await self.db.flush()
            logger.debug(
                "EventRouter.route: created %d deliveries for event_type=%s",
                len(deliveries), event.event_type.value,
            )
        return deliveries

    async def _get_existing_delivery(
        self, event_id: uuid.UUID, subscriber_id: uuid.UUID
    ) -> Optional[AIEventDelivery]:
        stmt = select(AIEventDelivery).where(
            AIEventDelivery.event_id == event_id,
            AIEventDelivery.subscriber_id == subscriber_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
