import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

from app.db.base import Base
from app.models.enums import TraceStatus


class AIToolTrace(Base):
    """Records every tool call: input, output, duration, retries.

    ADR-016: Immutable child span. Maps exactly to an OTel Span.
    """
    __tablename__ = "ai_tool_traces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_trace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_execution_traces.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    span_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, default=uuid.uuid4)
    parent_span_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    component: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    tool_name: Mapped[str] = mapped_column(String(200), nullable=False)
    arguments_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)
    result_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    status: Mapped[TraceStatus] = mapped_column(
        SQLEnum(TraceStatus, name="trace_status", native_enum=False, create_constraint=False),
        nullable=False,
        default=TraceStatus.STARTED
    )

    error_type: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stack_trace: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
