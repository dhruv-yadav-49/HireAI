"""
app/models/governance_policy.py

Per-organization governance policy with configurable risk thresholds.

ADR-022: Configurable Risk Appetite — thresholds belong to org policy,
not application code. Different orgs (Healthcare vs. Startup) tune
independently.

CTO refinement #5: policies are versioned and immutable. A new record is
created on every update — the previous version is retained for audit.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

from app.db.base import Base
from app.models.enums import PolicyPackType


class GovernancePolicy(Base):
    """Per-organization governance policy (versioned, immutable records).

    rules_json schema:
    {
        "permit_threshold": 0.25,
        "escalate_threshold": 0.65,
        "block_threshold": 0.85,
        "auto_approve_below": 0.20,
        "governed_actions": ["email_send", "delete_lead", "export_data", ...],
        "approval_expires_hours": 24,
        "pack_type": "DEFAULT"
    }
    """
    __tablename__ = "governance_policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # NULL = global default; org-specific overrides win
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    pack_type: Mapped[PolicyPackType] = mapped_column(
        SQLEnum(PolicyPackType, name="policy_pack_type", native_enum=False, create_constraint=False),
        nullable=False,
        default=PolicyPackType.DEFAULT,
    )

    # CTO refinement #5: versioned, immutable
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    rules_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    # No updated_at — new version record is created on change (ADR-022)
