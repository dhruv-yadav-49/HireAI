from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import EventType
from app.events.event_store import EventStore
from app.events.event_router import EventRouter
from app.events.event_dispatcher import EventDispatcher

logger = logging.getLogger(__name__)


class EventPublisher:
    """Single entry point for publishing domain events.

    Combines EventStore (write to outbox), EventRouter (fan-out to
    subscriber delivery records), and EventDispatcher (invoke handlers).

    ADR-020: Transactional Outbox, Publisher Interface (CTO refinement #4).
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._store = EventStore(db)
        self._router = EventRouter(db)
        self._dispatcher = EventDispatcher(db)

    async def publish(
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
    ) -> None:
        """Publishes a domain event end-to-end within the current DB transaction:

        1. Appends an immutable event record to the outbox.
        2. Routes the event to all active subscriber deliveries.
        3. Dispatches (calls handler) for each delivery.

        If there are no subscribers registered, the event is still stored
        in the outbox for auditability and future replay.
        """
        logger.info(
            "EventPublisher.publish event_type=%s org=%s", event_type.value, org_id
        )

        # Step 1 — Write to outbox (transactional)
        event = await self._store.append(
            org_id=org_id,
            event_type=event_type,
            payload=payload,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            event_version=event_version,
            schema_version=schema_version,
        )

        # Step 2 — Fan-out to subscriber deliveries
        deliveries = await self._router.route(event)

        if not deliveries:
            logger.debug(
                "EventPublisher.publish: no subscribers for %s, event stored for audit",
                event_type.value,
            )
            return

        # Step 3 — Dispatch handlers
        await self._dispatcher.dispatch(event)

        logger.info(
            "EventPublisher.publish: completed event_type=%s event_key=%s deliveries=%d",
            event_type.value, event.event_key, len(deliveries),
        )
