import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RetrievalFeedback(Base):
    """Stores user-supplied feedback on context retrieved for conversations."""

    __tablename__ = "retrieval_feedbacks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("retrieval_logs.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_feedback: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., 'HELPFUL', 'NOT_HELPFUL'
    feedback_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
