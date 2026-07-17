import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AgentType, AgentTaskStatus


class AIAgentTask(Base):
    """Represents a delegated task within a collaborative session."""

    __tablename__ = "ai_agent_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_agent_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    assigned_agent: Mapped[AgentType] = mapped_column(
        SQLEnum(AgentType, name="agent_type", native_enum=False),
        nullable=False,
    )
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[AgentTaskStatus] = mapped_column(
        SQLEnum(AgentTaskStatus, name="agent_task_status", native_enum=False),
        nullable=False,
        default=AgentTaskStatus.CREATED,
    )
    priority: Mapped[str] = mapped_column(String(50), default="MEDIUM", nullable=False)
    parent_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_agent_tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    result_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
