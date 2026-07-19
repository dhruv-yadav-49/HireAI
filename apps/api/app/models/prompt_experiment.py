"""
app/models/prompt_experiment.py

PromptExperiment record storing individual prompt trial executions.

CTO Refinement #3: Versioning (experiment_version, runtime_version, provider_version).
CTO Refinement #4: Normalized metrics output structure.
CTO Refinement #6: Hash tracking (prompt_hash, compiled_prompt_hash).
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PromptExperiment(Base):
    """Execution result record for a single prompt trial in an experiment."""

    __tablename__ = "prompt_experiments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("playground_experiments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Hashes & Versions
    prompt_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    experiment_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    runtime_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0")
    provider_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0")

    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    compiled_prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Parameters & Prompt
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)

    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    output_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Metrics
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    token_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    evaluation_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    governance_decision: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # CTO Refinement #4: Normalized metrics output
    normalized_metrics_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
