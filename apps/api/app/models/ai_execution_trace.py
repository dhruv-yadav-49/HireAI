import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, Numeric, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

from app.db.base import Base
from app.models.enums import TraceStatus, AgentType, TraceSamplingMode


class AIExecutionTrace(Base):
    """Top-level envelope for one complete AI execution. Every child trace links back here.

    ADR-016: Immutable, append-only. Mirrors OpenTelemetry Trace concept.
    """
    __tablename__ = "ai_execution_traces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    # OpenTelemetry span hierarchy
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, default=uuid.uuid4, index=True)
    span_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, default=uuid.uuid4)
    parent_span_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Correlation
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    execution_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    correlation_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    causation_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Agent context
    agent_type: Mapped[AgentType] = mapped_column(
        SQLEnum(AgentType, name="agent_type", native_enum=False),
        nullable=False
    )
    component: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Status & sampling
    status: Mapped[TraceStatus] = mapped_column(
        SQLEnum(TraceStatus, name="trace_status", native_enum=False, create_constraint=False),
        nullable=False,
        default=TraceStatus.STARTED
    )
    sampling_mode: Mapped[TraceSamplingMode] = mapped_column(
        SQLEnum(TraceSamplingMode, name="trace_sampling_mode", native_enum=False, create_constraint=False),
        nullable=False,
        default=TraceSamplingMode.FULL
    )

    # Timing
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    total_latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Aggregated costs
    total_cost: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Error diagnostics
    error_type: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stack_trace: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
