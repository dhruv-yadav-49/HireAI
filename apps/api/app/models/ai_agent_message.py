import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AgentType, MessageType


class AIAgentMessage(Base):
    """Stores inter-agent communications exchanging requests, responses, events, and handoffs."""

    __tablename__ = "ai_agent_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_agent_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_agent: Mapped[AgentType] = mapped_column(
        SQLEnum(AgentType, name="agent_type", native_enum=False),
        nullable=False,
    )
    to_agent: Mapped[AgentType] = mapped_column(
        SQLEnum(AgentType, name="agent_type", native_enum=False),
        nullable=False,
    )
    message_type: Mapped[MessageType] = mapped_column(
        SQLEnum(MessageType, name="message_type", native_enum=False),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    correlation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    causation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
