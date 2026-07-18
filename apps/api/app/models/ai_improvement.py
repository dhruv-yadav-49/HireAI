import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Float, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

from app.db.base import Base
from app.models.enums import ImprovementType, SuggestionStatus


class AIImprovement(Base):
    """Stores generated configuration improvements along with audit-trail evidence links.

    ADR-018: Explainable Suggestions, safe versioning.
    CTO refinement #2: status lifecycle (NEW, ANALYZED, PROPOSED, APPROVED, DEPLOYED, REJECTED).
    CTO refinement #3: pattern vs deployment confidence.
    CTO refinement #4: traceability JSONB ids list.
    """
    __tablename__ = "ai_improvements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    improvement_type: Mapped[ImprovementType] = mapped_column(
        SQLEnum(ImprovementType, name="improvement_type", native_enum=False),
        nullable=False
    )

    current_version: Mapped[str] = mapped_column(String(50), nullable=False)
    proposed_version: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    # Confidences (CTO refinement #3)
    pattern_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    deployment_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    # Status (CTO refinement #2)
    status: Mapped[SuggestionStatus] = mapped_column(
        SQLEnum(SuggestionStatus, name="suggestion_status", native_enum=False, create_constraint=False),
        nullable=False,
        default=SuggestionStatus.NEW
    )

    # Evidence links (CTO refinement #4)
    supporting_evaluation_ids: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=list)
    supporting_feedback_ids: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=list)
    supporting_trace_ids: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
