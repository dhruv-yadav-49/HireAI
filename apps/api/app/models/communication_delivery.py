import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import DeliveryEvent


class CommunicationDelivery(Base):
    """Audit trail events logs representing delivery updates (sent, delivered, failed, read, opened, etc.)."""

    __tablename__ = "communication_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    communication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("communications.id", ondelete="CASCADE"),
        nullable=False,
    )
    event: Mapped[DeliveryEvent] = mapped_column(
        SQLEnum(DeliveryEvent, name="delivery_event", native_enum=False),
        nullable=False,
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    provider_response: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
