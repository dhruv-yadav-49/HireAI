import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import MessageRole, AIProvider


class AIMessage(Base):
    """The granular message log exchange between the system/user/assistant and tools."""

    __tablename__ = "ai_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[MessageRole] = mapped_column(
        SQLEnum(MessageRole, name="message_role", native_enum=False),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Auditing metrics
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    response_time_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    finish_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cached: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Provider response logs snapshot
    raw_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    provider: Mapped[AIProvider] = mapped_column(
        SQLEnum(AIProvider, name="ai_provider", native_enum=False),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(String(100), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AITokenUsage(Base):
    """The granular cost, cache hit ratios, and token usage log per generation step."""

    __tablename__ = "ai_token_usages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_messages.id", ondelete="CASCADE"),
        nullable=True,
    )
    
    provider: Mapped[AIProvider] = mapped_column(
        SQLEnum(AIProvider, name="ai_provider", native_enum=False),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(String(100), nullable=False)

    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cached_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reasoning_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost: Mapped[float] = mapped_column(
        Numeric(precision=10, scale=5), default=0.00000, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
