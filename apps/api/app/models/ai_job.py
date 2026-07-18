import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

from app.db.base import Base
from app.models.enums import AIJobStatus, QueueType


class AIJob(Base):
    """Tracks asynchronous task executions, idempotency, leases, retries, and UX progress.

    ADR-019: Asynchronous by Default, Lease-Based Ownership, Idempotent Execution.
    """
    __tablename__ = "ai_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    job_type: Mapped[str] = mapped_column(String(100), nullable=False)

    status: Mapped[AIJobStatus] = mapped_column(
        SQLEnum(AIJobStatus, name="ai_job_status", native_enum=False, create_constraint=False),
        nullable=False,
        default=AIJobStatus.QUEUED
    )

    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=10)  # default normal=10
    queue_name: Mapped[QueueType] = mapped_column(
        SQLEnum(QueueType, name="queue_type", native_enum=False, create_constraint=False),
        nullable=False,
        default=QueueType.DEFAULT
    )

    # Ownership & Identification (CTO refinement #4)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    requested_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    source: Mapped[str] = mapped_column(String(100), nullable=False, default="API")
    client_version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0")

    # Idempotency fields (CTO refinement #3)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True, index=True)
    request_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Observability & Execution links
    execution_trace_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_execution_traces.id", ondelete="SET NULL"),
        nullable=True
    )
    worker_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_workers.id", ondelete="SET NULL"),
        nullable=True
    )

    # Retries budgets & status (CTO refinement #7)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    retry_budget: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    retry_consumed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # UX Progress reporting (CTO refinement #9)
    progress_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    current_step: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    total_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Lease parameters for high-availability crashes (CTO refinement #1)
    lease_owner: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
