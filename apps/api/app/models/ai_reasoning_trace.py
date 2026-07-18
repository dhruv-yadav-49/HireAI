import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AIReasoningTrace(Base):
    """Stores what the ReasoningEngine concluded about a lead/goal.

    ADR-016: Immutable child span. Captures the 'why' behind AI decisions.
    """
    __tablename__ = "ai_reasoning_traces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_trace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_execution_traces.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    span_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, default=uuid.uuid4)
    parent_span_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    component: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, default="ReasoningEngine")
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    priority: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    risk: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    expected_outcome: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    error_type: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
