import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, DateTime, Boolean, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

from app.db.base import Base
from app.models.enums import PIIType


class PIIIncident(Base):
    """Records when PII is detected in platform data.

    ADR-021: Privacy by Default — every detection is tracked for compliance
    and incident response. Masked flag records whether the value was redacted.
    """
    __tablename__ = "pii_incidents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    pii_type: Mapped[PIIType] = mapped_column(
        SQLEnum(PIIType, name="pii_type", native_enum=False, create_constraint=False),
        nullable=False,
        index=True,
    )

    # Where in the platform the PII was detected
    location: Mapped[str] = mapped_column(String(500), nullable=False)

    # Risk level: 0.0 – 1.0
    severity: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)

    masked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Optional: which request this occurred on
    request_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
