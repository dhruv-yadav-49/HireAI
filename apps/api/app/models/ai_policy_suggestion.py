import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

from app.db.base import Base
from app.models.enums import SuggestionStatus


class AIPolicySuggestion(Base):
    """Stores safety rule adjustments suggested for policy rules.

    CTO refinement #10: bundle_id grouping.
    CTO refinement #11: approval_id FK.
    """
    __tablename__ = "ai_policy_suggestions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    policy_name: Mapped[str] = mapped_column(String(200), nullable=False)
    current_rule: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_rule: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[SuggestionStatus] = mapped_column(
        SQLEnum(SuggestionStatus, name="suggestion_status", native_enum=False, create_constraint=False),
        nullable=False,
        default=SuggestionStatus.NEW
    )

    bundle_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    
    # Governance alignment (reusing approval framework)
    approval_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_approvals.id", ondelete="SET NULL"),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
