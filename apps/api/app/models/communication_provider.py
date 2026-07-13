import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, String, Index, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import ProviderType, CommunicationChannel


class CommunicationProvider(Base):
    """Configuration table for dynamic communication providers (SMTP, Twilio, Meta Cloud, etc.)."""

    __tablename__ = "communication_providers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_type: Mapped[ProviderType] = mapped_column(
        SQLEnum(ProviderType, name="provider_type", native_enum=False),
        nullable=False,
    )
    channel: Mapped[CommunicationChannel] = mapped_column(
        SQLEnum(CommunicationChannel, name="communication_channel", native_enum=False),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Encrypted credentials (e.g. SMTP password, Meta API tokens)
    credentials_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    configuration_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    capabilities_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    health_status: Mapped[str] = mapped_column(String(50), default="UNKNOWN", nullable=False)

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
        Index(
            "uq_default_provider_channel",
            "organization_id",
            "channel",
            unique=True,
            postgresql_where="is_default = true AND enabled = true",
        ),
    )
