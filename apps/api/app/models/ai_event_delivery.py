import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, DateTime, ForeignKey, TEXT
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

from app.db.base import Base
from app.models.enums import EventStatus


class AIEventDelivery(Base):
    """Tracks delivery status, retry attempts, lease-locks, and DLQ logs for event dispatches.

    ADR-020: At-Least-Once Delivery, Subscriber Isolation.
    """
    __tablename__ = "ai_event_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    subscriber_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_event_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    status: Mapped[EventStatus] = mapped_column(
        SQLEnum(EventStatus, name="event_status", native_enum=False, create_constraint=False),
        nullable=False,
        default=EventStatus.PENDING,
        index=True
    )

    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_error: Mapped[Optional[str]] = mapped_column(TEXT, nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # DLQ Metadata (CTO refinement #8)
    dead_letter_reason: Mapped[Optional[str]] = mapped_column(TEXT, nullable=True)
    failed_subscriber: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    failed_attempt: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Event Processing Lease (CTO refinement #2)
    lease_owner: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Subscriber Idempotency Tracking (CTO refinement #5)
    processed_event_key: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
