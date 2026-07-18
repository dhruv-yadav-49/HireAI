import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, Float, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

from app.db.base import Base
from app.models.enums import WorkerStatus


class AIWorker(Base):
    """Tracks active worker daemon resources, stats, and registration lifetimes.

    ADR-019: Worker Independence, Scalability.
    """
    __tablename__ = "ai_workers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hostname: Mapped[str] = mapped_column(String(200), nullable=False)
    worker_name: Mapped[str] = mapped_column(String(100), nullable=False)

    status: Mapped[WorkerStatus] = mapped_column(
        SQLEnum(WorkerStatus, name="worker_status", native_enum=False, create_constraint=False),
        nullable=False,
        default=WorkerStatus.STARTING
    )

    # Worker Capabilities (CTO refinement #5)
    supported_agents: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=list)
    supported_models: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=list)
    supported_tools: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=list)
    max_parallel_jobs: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Current work & Heartbeat health metrics (CTO refinement #6)
    current_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    cpu_usage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    memory_usage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    running_jobs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    queue_latency: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Crash recovery metrics (CTO refinement #3)
    last_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    restart_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shutdown_reason: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    heartbeat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0")

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
