"""
app/models/policy_violation.py

Individual policy violation record.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

from app.db.base import Base
from app.models.enums import ComplianceFramework, ViolationSeverity


class PolicyViolation(Base):
    """Detailed record of a specific governance policy violation."""

    __tablename__ = "policy_violations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    governance_decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("governance_decisions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
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

    control_id: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[ViolationSeverity] = mapped_column(
        SQLEnum(
            ViolationSeverity,
            name="violation_severity",
            native_enum=False,
            create_constraint=False,
        ),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(Text, nullable=False)
    remediation_hint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
