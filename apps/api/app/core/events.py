import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Protocol


@dataclass(frozen=True)
class DomainEvent:
    event_name: str
    tenant_id: uuid.UUID
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    request_id: Optional[uuid.UUID] = None
    actor_id: Optional[uuid.UUID] = None
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    payload: dict[str, Any] = field(default_factory=dict)


class DomainEventPublisher(Protocol):
    async def publish(self, event: DomainEvent) -> None:
        """Publishes a domain event asynchronously to the event broker."""
        ...


class NoOpEventPublisher:
    """Default No-Op event publisher for Sprint 3.
    Replaced by Redis Streams / Message Brokers in subsequent sprints.
    """
    async def publish(self, event: DomainEvent) -> None:
        # Dev environment log placeholder can go here if needed.
        pass


# Global publisher registration
_current_publisher: DomainEventPublisher = NoOpEventPublisher()


def get_event_publisher() -> DomainEventPublisher:
    return _current_publisher


def set_event_publisher(publisher: DomainEventPublisher) -> None:
    global _current_publisher
    _current_publisher = publisher
