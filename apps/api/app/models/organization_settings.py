import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class OrganizationSettings(Base):
    """Singleton settings row per organization.

    There is exactly one row per organization. Never created via POST —
    the GET endpoint is idempotent (creates defaults on first access).
    PATCH uses day-level merge for business_hours.

    business_hours JSONB schema:
    {
        "monday":    {"enabled": true,  "start": "09:00", "end": "17:00"},
        "tuesday":   {"enabled": true,  "start": "09:00", "end": "17:00"},
        "wednesday": {"enabled": true,  "start": "09:00", "end": "17:00"},
        "thursday":  {"enabled": true,  "start": "09:00", "end": "17:00"},
        "friday":    {"enabled": true,  "start": "09:00", "end": "17:00"},
        "saturday":  {"enabled": false},
        "sunday":    {"enabled": false}
    }
    """

    __tablename__ = "organization_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    timezone: Mapped[str] = mapped_column(String(100), nullable=False, default="UTC")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")  # ISO 4217
    language: Mapped[str] = mapped_column(String(5), nullable=False, default="en")   # ISO 639-1

    # Per-day schedule JSONB — enabled flag + start/end times.
    # working_days is encoded within this field (enabled: false = closed).
    business_hours: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    email_signature: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
