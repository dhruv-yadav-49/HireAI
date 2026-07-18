import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Integer, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

from app.db.base import Base
from app.models.enums import FeedbackType, FeedbackCategory


class AIFeedback(Base):
    """Stores human feedback and labels for evaluations to guide learning optimization.

    CTO refinement #10: feedback_category specifies nature of the feedback (e.g., Wrong Answer, Too Slow, Hallucination).
    """
    __tablename__ = "ai_feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_evaluations.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    feedback_type: Mapped[FeedbackType] = mapped_column(
        SQLEnum(FeedbackType, name="feedback_type", native_enum=False, create_constraint=False),
        nullable=False
    )
    feedback_category: Mapped[FeedbackCategory] = mapped_column(
        SQLEnum(FeedbackCategory, name="feedback_category", native_enum=False, create_constraint=False),
        nullable=False,
        default=FeedbackCategory.OTHER
    )

    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1 to 5 stars
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
