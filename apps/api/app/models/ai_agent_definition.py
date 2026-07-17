import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, Integer, String, Text, func, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AgentType


class AIAgentDefinition(Base):
    """Persisted definitions for all registered AI Employees in the platform registry."""

    __tablename__ = "ai_agent_definitions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_type: Mapped[AgentType] = mapped_column(
        SQLEnum(AgentType, name="agent_type", native_enum=False),
        nullable=False,
        unique=True,
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    supported_goals: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    required_tools: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    max_parallel_tasks: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
