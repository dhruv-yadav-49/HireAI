import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, Boolean, DateTime, Float, TEXT
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

from app.db.base import Base
from app.models.enums import AuditAction


class AuditLog(Base):
    """Immutable, append-only security audit trail.

    ADR-021: Immutable Audit — records are written once and never modified.
    No updated_at column by design (write-once contract).
    CTO refinement #6: request_id, correlation_id, success, duration_ms
    allow audit events to be correlated with execution traces and jobs.
    """
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    # What happened
    action: Mapped[AuditAction] = mapped_column(
        SQLEnum(AuditAction, name="audit_action", native_enum=False, create_constraint=False),
        nullable=False,
        index=True,
    )
    resource_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Outcome (CTO refinement #6)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Request correlation (CTO refinement #6)
    request_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Network context
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Flexible event payload
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Immutable timestamp — no updated_at by design
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
