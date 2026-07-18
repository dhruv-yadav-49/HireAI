from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_event import AIEvent
from app.models.ai_event_subscription import AIEventSubscription
from app.models.ai_event_delivery import AIEventDelivery
from app.models.enums import EventType, EventStatus

logger = logging.getLogger(__name__)


class EventRepository:
    """Data access layer for the event bus tables.

    Provides reads and administrative operations (subscription management,
    replay queries, DLQ inspection) separate from the write path in
    EventStore / EventRouter.

    ADR-020: Repository Pattern, Replay Safety (CTO refinements #9, #12).
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ──────────────────────────────────────────────────────────────────────────
    # AIEvent queries
    # ──────────────────────────────────────────────────────────────────────────

    async def get_event_by_id(self, event_id: uuid.UUID) -> Optional[AIEvent]:
        stmt = select(AIEvent).where(AIEvent.id == event_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_event_by_key(self, event_key: uuid.UUID) -> Optional[AIEvent]:
        """Look up by stable external key (CTO refinement #2)."""
        stmt = select(AIEvent).where(AIEvent.event_key == event_key)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_events(
        self,
        org_id: uuid.UUID,
        event_type: Optional[EventType] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[AIEvent]:
        stmt = select(AIEvent).where(
            AIEvent.organization_id == org_id,
            AIEvent.archived == False,
        )
        if event_type:
            stmt = stmt.where(AIEvent.event_type == event_type)
        if since:
            stmt = stmt.where(AIEvent.published_at >= since)
        stmt = stmt.order_by(AIEvent.sequence_number.asc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_replay_events(
        self,
        org_id: uuid.UUID,
        event_type: EventType,
        from_sequence: int,
        to_sequence: Optional[int] = None,
        limit: int = 500,
    ) -> list[AIEvent]:
        """Returns events in sequence order for replay (CTO refinement #9)."""
        stmt = select(AIEvent).where(
            AIEvent.organization_id == org_id,
            AIEvent.event_type == event_type,
            AIEvent.sequence_number >= from_sequence,
            AIEvent.archived == False,
        )
        if to_sequence is not None:
            stmt = stmt.where(AIEvent.sequence_number <= to_sequence)
        stmt = stmt.order_by(AIEvent.sequence_number.asc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def archive_expired_events(self) -> int:
        """Archives events past their expiry date. Returns count archived."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(AIEvent)
            .where(
                AIEvent.expires_at <= now,
                AIEvent.archived == False,
            )
            .values(archived=True)
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        count = result.rowcount
        logger.info("EventRepository.archive_expired_events: archived %d events", count)
        return count

    # ──────────────────────────────────────────────────────────────────────────
    # AIEventSubscription management
    # ──────────────────────────────────────────────────────────────────────────

    async def get_subscription(
        self, subscriber_name: str, event_type: EventType
    ) -> Optional[AIEventSubscription]:
        stmt = select(AIEventSubscription).where(
            AIEventSubscription.subscriber_name == subscriber_name,
            AIEventSubscription.event_type == event_type,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_subscription(
        self,
        subscriber_name: str,
        event_type: EventType,
        *,
        subscriber_version: str = "v1",
        handler_version: str = "v1",
        retry_limit: int = 3,
        timeout_seconds: int = 60,
        enabled: bool = True,
    ) -> AIEventSubscription:
        """Idempotent upsert used during app startup to seed subscriptions
        (CTO refinement #13)."""
        existing = await self.get_subscription(subscriber_name, event_type)
        if existing:
            # Update metadata in case versions changed
            stmt = (
                update(AIEventSubscription)
                .where(AIEventSubscription.id == existing.id)
                .values(
                    subscriber_version=subscriber_version,
                    handler_version=handler_version,
                    retry_limit=retry_limit,
                    timeout_seconds=timeout_seconds,
                    enabled=enabled,
                )
            )
            await self.db.execute(stmt)
            await self.db.flush()
            await self.db.refresh(existing)
            return existing

        sub = AIEventSubscription(
            id=uuid.uuid4(),
            subscriber_name=subscriber_name,
            event_type=event_type,
            subscriber_version=subscriber_version,
            handler_version=handler_version,
            retry_limit=retry_limit,
            timeout_seconds=timeout_seconds,
            enabled=enabled,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(sub)
        await self.db.flush()
        logger.info(
            "EventRepository.upsert_subscription: registered %s → %s",
            subscriber_name, event_type.value,
        )
        return sub

    async def list_subscriptions(
        self, event_type: Optional[EventType] = None
    ) -> list[AIEventSubscription]:
        stmt = select(AIEventSubscription)
        if event_type:
            stmt = stmt.where(AIEventSubscription.event_type == event_type)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ──────────────────────────────────────────────────────────────────────────
    # AIEventDelivery queries
    # ──────────────────────────────────────────────────────────────────────────

    async def list_dead_letter(
        self, limit: int = 100
    ) -> list[AIEventDelivery]:
        """Returns all deliveries in DEAD_LETTER status for operational inspection."""
        stmt = (
            select(AIEventDelivery)
            .where(AIEventDelivery.status == EventStatus.DEAD_LETTER)
            .order_by(AIEventDelivery.failed_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_stale_leases(
        self, grace_seconds: int = 30
    ) -> list[AIEventDelivery]:
        """Returns deliveries whose lease has expired — indicates crashed workers."""
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=grace_seconds)
        stmt = select(AIEventDelivery).where(
            AIEventDelivery.lease_owner.is_not(None),
            AIEventDelivery.lease_expires_at <= cutoff,
            AIEventDelivery.status.in_([EventStatus.PENDING, EventStatus.RETRYING]),
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def requeue_stale_leases(self) -> int:
        """Resets expired leases back to RETRYING so another dispatcher can pick
        them up (CTO refinement #2 — lease expiry / requeue)."""
        stale = await self.list_stale_leases()
        count = 0
        for delivery in stale:
            stmt = (
                update(AIEventDelivery)
                .where(AIEventDelivery.id == delivery.id)
                .values(
                    lease_owner=None,
                    lease_expires_at=None,
                    status=EventStatus.RETRYING,
                )
            )
            await self.db.execute(stmt)
            count += 1
        if count:
            await self.db.flush()
            logger.info("EventRepository.requeue_stale_leases: requeued %d deliveries", count)
        return count

    async def delivery_counts_by_status(self) -> dict[str, int]:
        """Returns a breakdown of delivery counts per status."""
        stmt = (
            select(AIEventDelivery.status, func.count(AIEventDelivery.id))
            .group_by(AIEventDelivery.status)
        )
        result = await self.db.execute(stmt)
        return {str(row[0]): row[1] for row in result.all()}
