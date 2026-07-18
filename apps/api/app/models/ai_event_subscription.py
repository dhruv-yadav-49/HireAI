import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

from app.db.base import Base
from app.models.enums import EventType


class AIEventSubscription(Base):
    """Tracks active event subscribers and their versions.

    ADR-020: Versioned Contracts, Subscriber Isolation.
    """
    __tablename__ = "ai_event_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscriber_name: Mapped[str] = mapped_column(String(100), nullable=False)
    subscriber_version: Mapped[str] = mapped_column(String(20), nullable=False, default="v1")
    handler_version: Mapped[str] = mapped_column(String(20), nullable=False, default="v1")

    event_type: Mapped[EventType] = mapped_column(
        SQLEnum(EventType, name="event_type", native_enum=False, create_constraint=False),
        nullable=False,
        index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    retry_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
