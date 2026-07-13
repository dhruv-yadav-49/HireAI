import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import RetrievalSource


class RetrievalLog(Base):
    """Logs semantic search and context retrieval operations for performance auditing."""

    __tablename__ = "retrieval_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    query_embedding_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    retrieval_source: Mapped[RetrievalSource] = mapped_column(
        String(50), default=RetrievalSource.HYBRID, nullable=False
    )
    retrieved_chunks: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    retrieval_latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    embedding_latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    vector_search_latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    crm_latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    memory_latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rerank_latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    total_chunks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
