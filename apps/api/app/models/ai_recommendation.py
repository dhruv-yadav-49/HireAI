import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import RecommendationPriority, RecommendationStatus


class AIRecommendation(Base):
    """Stores actionable recommendations suggested by the AI Business Analyst."""

    __tablename__ = "ai_recommendations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    recommendation_type: Mapped[str] = mapped_column(String(100), nullable=False)
    priority: Mapped[RecommendationPriority] = mapped_column(
        SQLEnum(RecommendationPriority, name="recommendation_priority", native_enum=False),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    expected_impact: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_agents: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[RecommendationStatus] = mapped_column(
        SQLEnum(RecommendationStatus, name="recommendation_status", native_enum=False),
        nullable=False,
        default=RecommendationStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
