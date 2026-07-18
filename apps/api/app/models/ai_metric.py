import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

from app.db.base import Base
from app.models.enums import MetricType, AgentType


class AIMetric(Base):
    """Flat per-execution metric row for fast analytics queries.

    Written once after execution completes. Never updated.
    CTO refinement #8: extended metric types including planning, policy, retrieval.
    """
    __tablename__ = "ai_metrics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_trace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_execution_traces.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    agent_type: Mapped[AgentType] = mapped_column(
        SQLEnum(AgentType, name="agent_type", native_enum=False),
        nullable=False, index=True
    )
    metric_type: Mapped[MetricType] = mapped_column(
        SQLEnum(MetricType, name="metric_type", native_enum=False, create_constraint=False),
        nullable=False
    )

    value_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    value_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    value_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
