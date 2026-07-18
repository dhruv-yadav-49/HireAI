import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AIPromptTrace(Base):
    """Records the compiled prompt sent to the LLM, token counts, and hash.

    ADR-016: Immutable. Maps to an OpenTelemetry child Span of execution trace.
    """
    __tablename__ = "ai_prompt_traces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_trace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_execution_traces.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    # OTel span hierarchy
    span_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, default=uuid.uuid4)
    parent_span_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    component: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, default="PromptEngine")
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Prompt content
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    compiled_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    variables_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)
    prompt_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Token breakdown (CTO refinement #7)
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cached_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reasoning_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_type: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
