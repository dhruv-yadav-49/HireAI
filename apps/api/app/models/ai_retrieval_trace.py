import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AIRetrievalTrace(Base):
    """Records context retrieval results broken down by source with per-source timing.

    CTO refinement #6: separate timings per retrieval source.
    ADR-016: Immutable child span.
    """
    __tablename__ = "ai_retrieval_traces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_trace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_execution_traces.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    span_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, default=uuid.uuid4)
    parent_span_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    component: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, default="RetrievalService")
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    query: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    retrieved_memories_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=list)
    retrieved_knowledge_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=list)
    retrieved_crm_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=list)
    vector_hit_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Per-source timings
    memory_latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    crm_latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    knowledge_latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    vector_search_latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_retrieval_latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    error_type: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
