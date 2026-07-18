import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, Float, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

from app.db.base import Base
from app.models.enums import EvaluationStatus, QualityGrade, AgentType


class AIEvaluation(Base):
    """Top-level evaluation correlating an observability trace to an objective grade.

    ADR-017: Versioned Scoring, Explainable Scores, and Passive Assessment.
    """
    __tablename__ = "ai_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    execution_trace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_execution_traces.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    agent_type: Mapped[AgentType] = mapped_column(
        SQLEnum(AgentType, name="agent_type", native_enum=False),
        nullable=False
    )

    status: Mapped[EvaluationStatus] = mapped_column(
        SQLEnum(EvaluationStatus, name="evaluation_status", native_enum=False, create_constraint=False),
        nullable=False,
        default=EvaluationStatus.PENDING
    )

    overall_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quality_grade: Mapped[Optional[QualityGrade]] = mapped_column(
        SQLEnum(QualityGrade, name="quality_grade", native_enum=False, create_constraint=False),
        nullable=True
    )

    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Versioning & Explainability (CTO refinements #1, #4, #11, #15)
    evaluation_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    evaluation_model: Mapped[str] = mapped_column(String(100), nullable=False, default="RULE_ENGINE_V1")
    evaluation_trace: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)
    evaluation_timeline: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)
    eligible_for_training: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
