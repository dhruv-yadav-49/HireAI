import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AIActionType, AIActionStatus


class AIAction(Base):
    """Execution step trace representing a single tool or reasoning invocation in a plan's execution queue."""

    __tablename__ = "ai_actions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    depends_on_action_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_actions.id", ondelete="SET NULL"),
        nullable=True,
    )
    action_type: Mapped[AIActionType] = mapped_column(
        SQLEnum(AIActionType, name="ai_action_type", native_enum=False),
        nullable=False,
    )
    tool_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[AIActionStatus] = mapped_column(
        SQLEnum(AIActionStatus, name="ai_action_status", native_enum=False),
        nullable=False,
        default=AIActionStatus.PENDING,
    )
    input_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    attempt_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
