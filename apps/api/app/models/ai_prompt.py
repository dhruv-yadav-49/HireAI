import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, BaseModel


class AIPrompt(BaseModel):
    """Reusable template configs representing prompt segments (System, CRM contexts, custom memory rules)."""

    __tablename__ = "ai_prompts"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., 'SYSTEM', 'CONTEXT', 'MEMORY'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    variables_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AIPromptExecution(Base):
    """Execution history snapshot loggingcompiled prompts dispatched to LLM providers."""

    __tablename__ = "ai_prompt_executions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    compiled_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    variables_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256 hash of compiled string
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
