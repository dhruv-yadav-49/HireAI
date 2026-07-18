from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_event import AIEvent
from app.models.enums import EventType, EventStatus
from app.events.event_serializer import EventSerializer

logger = logging.getLogger(__name__)


class EventStore:
    """Transactional outbox: persists immutable domain events inside the
    same database transaction as the business operation.

    ADR-020: Immutable Events, Transactional Outbox (CTO refinement #4).
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _next_sequence_number(self, org_id: uuid.UUID) -> int:
        """Returns the next monotonic sequence number per organization
        for deterministic event ordering (CTO refinement #3)."""
        stmt = select(func.max(AIEvent.sequence_number)).where(
            AIEvent.organization_id == org_id
        )
        result = await self.db.execute(stmt)
        current_max = result.scalar_one_or_none()
        return (current_max or 0) + 1

    async def append(
        self,
        org_id: uuid.UUID,
        event_type: EventType,
        payload: dict,
        *,
        aggregate_type: Optional[str] = None,
        aggregate_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[uuid.UUID] = None,
        causation_id: Optional[uuid.UUID] = None,
        event_version: int = 1,
        schema_version: str = "v1",
        expires_at: Optional[datetime] = None,
    ) -> AIEvent:
        """Appends an immutable event record to the outbox within the
        current database transaction.

        The caller is responsible for committing the surrounding transaction.
        """
        serialized_payload = EventSerializer.serialize(payload)
        sequence_number = await self._next_sequence_number(org_id)

        event = AIEvent(
            id=uuid.uuid4(),
            event_key=uuid.uuid4(),          # Stable external identity (CTO refinement #2)
            organization_id=org_id,
            event_type=event_type,
            event_version=event_version,
            schema_version=schema_version,
            sequence_number=sequence_number,  # Deterministic ordering (CTO refinement #3)
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload_json=serialized_payload,
            status=EventStatus.PENDING,
            published_at=datetime.now(timezone.utc),
            expires_at=expires_at,
            archived=False,
        )
        self.db.add(event)
        await self.db.flush()
        logger.debug(
            "EventStore.append event_type=%s event_key=%s seq=%d",
            event_type.value, event.event_key, sequence_number
        )
        return event

    async def mark_delivered(self, event_id: uuid.UUID) -> None:
        """Marks an event as fully delivered once all subscriber deliveries
        have been successfully dispatched."""
        stmt = (
            update(AIEvent)
            .where(AIEvent.id == event_id)
            .values(status=EventStatus.DELIVERED)
        )
        await self.db.execute(stmt)
        await self.db.flush()

    async def mark_failed(self, event_id: uuid.UUID) -> None:
        """Marks an event as failed (DLQ-eligible)."""
        stmt = (
            update(AIEvent)
            .where(AIEvent.id == event_id)
            .values(status=EventStatus.FAILED)
        )
        await self.db.execute(stmt)
        await self.db.flush()

    async def get_pending_events(self, limit: int = 50) -> list[AIEvent]:
        """Fetches pending outbox events for the dispatcher to process."""
        stmt = (
            select(AIEvent)
            .where(AIEvent.status == EventStatus.PENDING, AIEvent.archived == False)
            .order_by(AIEvent.sequence_number.asc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
