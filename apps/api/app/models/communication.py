import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, SmallInteger, String, Text, Index, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    CommunicationChannel,
    CommunicationStatus,
    CommunicationPriority,
    CommunicationDirection,
    RecipientType,
)


class Communication(Base):
    """The Outbound/Inbound Communication Log representing Emails, WhatsApps, and SMSs."""

    __tablename__ = "communications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="SET NULL"),
        nullable=True,
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("communication_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("communication_providers.id", ondelete="SET NULL"),
        nullable=True,
    )

    channel: Mapped[CommunicationChannel] = mapped_column(
        SQLEnum(CommunicationChannel, name="communication_channel", native_enum=False),
        nullable=False,
    )
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_type: Mapped[RecipientType] = mapped_column(
        SQLEnum(RecipientType, name="recipient_type", native_enum=False),
        nullable=False,
    )
    direction: Mapped[CommunicationDirection] = mapped_column(
        SQLEnum(CommunicationDirection, name="communication_direction", native_enum=False),
        nullable=False,
        default=CommunicationDirection.OUTBOUND,
    )

    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    parent_communication_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # Rendering Snapshots
    rendered_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rendered_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    attachments_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    status: Mapped[CommunicationStatus] = mapped_column(
        SQLEnum(CommunicationStatus, name="communication_status", native_enum=False),
        nullable=False,
        default=CommunicationStatus.QUEUED,
    )
    priority: Mapped[CommunicationPriority] = mapped_column(
        SQLEnum(CommunicationPriority, name="communication_priority", native_enum=False),
        nullable=False,
        default=CommunicationPriority.NORMAL,
    )
    render_engine_version: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)

    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("uq_communication_idempotency", "organization_id", "idempotency_key", unique=True),
        Index("ix_communications_scheduled", "scheduled_at", postgresql_where="status = 'QUEUED'"),
        Index("ix_communications_conversation", "conversation_id"),
    )
