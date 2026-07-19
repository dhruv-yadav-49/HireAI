"""
app/models/compliance_report.py

Compliance report snapshot model.

CTO refinement #7: Event-driven aggregation — reports represent historical
compliance snapshots computed asynchronously from governance domain events.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, String
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

from app.db.base import Base
from app.models.enums import ComplianceFramework


class ComplianceReport(Base):
    """Compliance report snapshot for SOC2, ISO 27001, OWASP, etc."""

    __tablename__ = "compliance_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    framework: Mapped[ComplianceFramework] = mapped_column(
        SQLEnum(
            ComplianceFramework,
            name="compliance_framework",
            native_enum=False,
            create_constraint=False,
        ),
        nullable=False,
    )

    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    total_decisions: Mapped[int] = mapped_column(nullable=False, default=0)
    permitted_count: Mapped[int] = mapped_column(nullable=False, default=0)
    blocked_count: Mapped[int] = mapped_column(nullable=False, default=0)
    escalated_count: Mapped[int] = mapped_column(nullable=False, default=0)
    approved_count: Mapped[int] = mapped_column(nullable=False, default=0)
    rejected_count: Mapped[int] = mapped_column(nullable=False, default=0)

    score: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)

    controls_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    violations_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
