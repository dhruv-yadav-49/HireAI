import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, Float, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

from app.db.base import Base
from app.models.enums import AIJobStatus, JobFailureCategory


class AIJobResult(Base):
    """Stores execution outputs, token metrics, costs, failure categories, and retention dates.

    CTO refinement #8: Failure reason, failure category, last exception.
    CTO refinement #9: Retention limits (expires_at).
    """
    __tablename__ = "ai_job_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_jobs.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    status: Mapped[AIJobStatus] = mapped_column(
        SQLEnum(AIJobStatus, name="ai_job_status", native_enum=False, create_constraint=False),
        nullable=False
    )

    output_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Granular failures tracking (CTO refinement #8)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(250), nullable=True)
    failure_category: Mapped[Optional[JobFailureCategory]] = mapped_column(
        SQLEnum(JobFailureCategory, name="job_failure_category", native_enum=False, create_constraint=False),
        nullable=True
    )
    last_exception: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    execution_time_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    token_usage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Result retention data (CTO refinement #9)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
class AIJobEvent(Base):
    __tablename__ = "ai_job_events"
    id = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    event = mapped_column(String(100), nullable=False)
    timestamp = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    details_json = mapped_column(JSONB, nullable=False, default=dict)
