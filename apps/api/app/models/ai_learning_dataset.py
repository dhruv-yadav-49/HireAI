import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

from app.db.base import Base
from app.models.enums import AgentType


class AILearningDataset(Base):
    """Stores compiled inputs, outputs, and ratings for training AI employee optimizations.

    ADR-018: Immutable Learning Dataset.
    CTO refinement #1: Adds dataset_version and dataset_source columns.
    """
    __tablename__ = "ai_learning_datasets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    execution_trace_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_execution_traces.id", ondelete="CASCADE"),
        nullable=True, index=True
    )
    evaluation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_evaluations.id", ondelete="CASCADE"),
        nullable=True, index=True
    )
    feedback_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_feedback.id", ondelete="CASCADE"),
        nullable=True, index=True
    )

    agent_type: Mapped[AgentType] = mapped_column(
        SQLEnum(AgentType, name="agent_type", native_enum=False),
        nullable=False
    )

    input_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    expected_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Versioning & Source tracking (CTO refinement #1)
    dataset_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    dataset_source: Mapped[str] = mapped_column(String(50), nullable=False, default="EXECUTION")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
