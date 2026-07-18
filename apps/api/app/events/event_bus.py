from __future__ import annotations

import uuid
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import EventType
from app.events.event_publisher import EventPublisher

logger = logging.getLogger(__name__)


class EventBus:
    """Lightweight broker wrapper over EventPublisher.

    This class is the canonical surface that all application services
    use to publish events. It decouples callers from the internal
    Publisher/Store/Router/Dispatcher chain.

    ADR-020: Event Bus Broker, Transport Abstraction (CTO refinement #11).
    """

    def __init__(self, db: AsyncSession):
        self._publisher = EventPublisher(db)

    async def emit(
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
        """Emits a domain event on the bus.

        Internally delegates to EventPublisher.publish() which handles
        the transactional outbox, routing, and dispatcher steps.
        """
        await self._publisher.publish(
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
        logger.debug("EventBus.emit: %s emitted for org=%s", event_type.value, org_id)
