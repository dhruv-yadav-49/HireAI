import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

from app.db.base import Base
from app.models.enums import SecretType


class SecretReference(Base):
    """Stores metadata about secrets — never the secret value itself.

    ADR-021: Secret Abstraction — business code never directly accesses
    secret providers. This table tracks what secrets exist, their type,
    provider backend, and rotation schedule.
    """
    __tablename__ = "secret_references"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    secret_name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)

    secret_type: Mapped[SecretType] = mapped_column(
        SQLEnum(SecretType, name="secret_type", native_enum=False, create_constraint=False),
        nullable=False,
    )

    # Provider abstraction: "env", "vault", "aws", "azure"
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="env")

    # How often to rotate (days). NULL = no scheduled rotation
    rotation_period_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    last_rotated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
