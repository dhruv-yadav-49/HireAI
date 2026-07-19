"""
app/models/governance_decision.py

Immutable governance decision record.

ADR-022: Explainable Decisions — every record stores the contributing
risk factors, matched policy rules, and the final decision.
ADR-022: Versioned Policies — decision_version, risk_model_version, and
policy_version guarantee full reproducibility of the decision.

No updated_at — this model is append-only by architectural contract.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

from app.db.base import Base
from app.models.enums import GovernanceDecisionStatus, RiskLevel


class GovernanceDecision(Base):
    """Immutable governance decision.

    explanation_json schema:
    {
        "risk": {
            "action_type": 0.30,
            "pii_present": 0.25,
            "data_sensitivity": 0.10,
            "behavior": 0.05,
            "context": 0.02,
            "total": 0.72
        },
        "policy": ["GDPR-4", "SOC2-CC6.1"],
        "thresholds": {
            "permit": 0.25,
            "escalate": 0.65,
            "block": 0.85
        },
        "decision": "ESCALATE"
    }
    """
    __tablename__ = "governance_decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    ai_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Action metadata
    action_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    action_payload_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Risk
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[RiskLevel] = mapped_column(
        SQLEnum(RiskLevel, name="risk_level", native_enum=False, create_constraint=False),
        nullable=False,
    )

    # Decision
    decision_status: Mapped[GovernanceDecisionStatus] = mapped_column(
        SQLEnum(GovernanceDecisionStatus, name="governance_decision_status",
                native_enum=False, create_constraint=False),
        nullable=False,
    )

    # CTO refinement #3: structured explainability
    explanation_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # CTO refinement #2: versioning for reproducibility
    decision_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    risk_model_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0")
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    policy_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Correlation with 7C audit trail
    request_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
        default=lambda: datetime.now(timezone.utc),
    )
    # No updated_at — immutable by ADR-022
