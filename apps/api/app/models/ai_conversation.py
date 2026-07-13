import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, Float, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import ConversationStatus, AIRuntimeState, AIProvider


class AIConversation(Base):
    """The interactive runtime context tracking history sessions, cost budgets, and state progress."""

    __tablename__ = "ai_conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    status: Mapped[ConversationStatus] = mapped_column(
        SQLEnum(ConversationStatus, name="conversation_status", native_enum=False),
        nullable=False,
        default=ConversationStatus.ACTIVE,
    )
    runtime_state: Mapped[AIRuntimeState] = mapped_column(
        SQLEnum(AIRuntimeState, name="ai_runtime_state", native_enum=False),
        nullable=False,
        default=AIRuntimeState.IDLE,
    )

    # Immutable Agent Snapshots
    agent_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    agent_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider: Mapped[AIProvider | None] = mapped_column(
        SQLEnum(AIProvider, name="ai_provider", native_enum=False),
        nullable=True,
    )
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Loop protections and metadata
    tool_iterations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_tool_iterations: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    conversation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    runtime_metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    security_flags: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Cost / Token aggregates
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost: Mapped[float] = mapped_column(
        Numeric(precision=10, scale=5), default=0.00000, nullable=False
    )
    total_latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tool_calls_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
