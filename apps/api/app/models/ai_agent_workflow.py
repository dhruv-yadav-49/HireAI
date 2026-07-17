import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import SessionStatus


class AIAgentWorkflow(Base):
    """Tracks structured graph states and executions for multi-agent workflows."""

    __tablename__ = "ai_agent_workflows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_agent_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    workflow_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[SessionStatus] = mapped_column(
        SQLEnum(SessionStatus, name="session_status", native_enum=False),
        nullable=False,
        default=SessionStatus.ACTIVE,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
