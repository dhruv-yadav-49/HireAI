import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AIFeedbackSession(Base):
    """Groups related human feedback inputs for batch analysis."""
    __tablename__ = "ai_feedback_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    feedback_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
