import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Float, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

from app.db.base import Base
from app.models.enums import SuggestionStatus


class AIPromptSuggestion(Base):
    """Stores prompt template refactoring recommendations.

    CTO refinement #5: estimated_impact and affected_agents.
    CTO refinement #10: bundle_id grouping.
    CTO refinement #11: approval_id FK.
    """
    __tablename__ = "ai_prompt_suggestions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    prompt_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_prompts.id", ondelete="CASCADE"),
        nullable=True, index=True
    )

    current_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    pattern_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    deployment_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    status: Mapped[SuggestionStatus] = mapped_column(
        SQLEnum(SuggestionStatus, name="suggestion_status", native_enum=False, create_constraint=False),
        nullable=False,
        default=SuggestionStatus.NEW
    )

    # CTO refinements (#5, #10, #11)
    estimated_impact: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    affected_agents: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=list)
    bundle_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    
    # Governance alignment (reusing approval framework)
    approval_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_approvals.id", ondelete="SET NULL"),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
