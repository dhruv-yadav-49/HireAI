import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AIApprovalStatus


class AIApproval(Base):
    """Tracks human approval records for sensitive AI action execution overrides."""

    __tablename__ = "ai_approvals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    action_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_actions.id", ondelete="CASCADE"),
        nullable=False,
    )
    requested_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approval_type: Mapped[str] = mapped_column(String(50), default="MANAGER", nullable=False)
    status: Mapped[AIApprovalStatus] = mapped_column(
        SQLEnum(AIApprovalStatus, name="ai_approval_status", native_enum=False),
        nullable=False,
        default=AIApprovalStatus.PENDING,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
