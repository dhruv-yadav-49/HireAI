import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text, SmallInteger, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.models.enums import (
    ActorType,
    JobStatus,
    JobType,
    JobExecutionStatus,
    EntityType,
    ReminderType,
    ReminderStatus,
    NotificationChannel,
    RecipientType,
    NotificationPriority,
    NotificationStatus,
    NotificationProvider,
)


class ScheduledJob(Base):
    """Configuration table for scheduled recurring and system background jobs."""

    __tablename__ = "scheduled_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)
    job_type: Mapped[JobType] = mapped_column(
        SQLEnum(JobType, name="job_type", native_enum=False),
        nullable=False,
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    payload_version: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)

    status: Mapped[JobStatus] = mapped_column(
        SQLEnum(JobStatus, name="job_status", native_enum=False),
        nullable=False,
        default=JobStatus.ACTIVE,
    )
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timezone: Mapped[str | None] = mapped_column(String(100), nullable=True)

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    updated_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    executions = relationship(
        "JobExecution",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobExecution.started_at.desc()",
    )

    # Indexing next_run_at for fast ticks
    __table_args__ = (
        Index("ix_scheduled_jobs_next_run_at", "next_run_at", postgresql_where=(status == "ACTIVE")),
        Index("ix_scheduled_jobs_organization_id", "organization_id"),
    )


class JobExecution(Base):
    """Detailed audit run logs for job executions, retries, and failures."""

    __tablename__ = "job_executions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scheduled_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
    )
    status: Mapped[JobExecutionStatus] = mapped_column(
        SQLEnum(JobExecutionStatus, name="job_execution_status", native_enum=False),
        nullable=False,
        default=JobExecutionStatus.RUNNING,
    )
    execution_key: Mapped[str] = mapped_column(String(100), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    payload_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    scheduler_instance: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Metrics
    processed_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_reminders: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    published_events: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    queued_notifications: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    job = relationship("ScheduledJob", back_populates="executions")

    # Ensure idempotency per scheduled run
    __table_args__ = (
        Index("uq_job_executions_key", "job_id", "execution_key", unique=True),
    )


class Reminder(Base):
    """Task and lead inactivity reminders with unique constraints to prevent duplication."""

    __tablename__ = "reminders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_type: Mapped[EntityType] = mapped_column(
        SQLEnum(EntityType, name="entity_type", native_enum=False),
        nullable=False,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    reminder_type: Mapped[ReminderType] = mapped_column(
        SQLEnum(ReminderType, name="reminder_type", native_enum=False),
        nullable=False,
    )

    remind_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[ReminderStatus] = mapped_column(
        SQLEnum(ReminderStatus, name="reminder_status", native_enum=False),
        nullable=False,
        default=ReminderStatus.PENDING,
    )
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    created_by_type: Mapped[ActorType] = mapped_column(
        SQLEnum(ActorType, name="actor_type", native_enum=False),
        nullable=False,
        default=ActorType.SYSTEM,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Constraints and Indexing
    __table_args__ = (
        Index("ix_reminders_remind_at", "remind_at", postgresql_where=(status == "PENDING")),
        Index("uq_pending_reminders", "organization_id", "entity_type", "entity_id", "reminder_type", unique=True, postgresql_where=(status == "PENDING")),
        Index("ix_reminders_org_entity", "organization_id", "entity_type", "entity_id"),
    )


class NotificationQueue(Base):
    """Notification dispatch queue with priority and expiration checks."""

    __tablename__ = "notification_queue"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_type: Mapped[RecipientType] = mapped_column(
        SQLEnum(RecipientType, name="recipient_type", native_enum=False),
        nullable=False,
        default=RecipientType.EMAIL,
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        SQLEnum(NotificationChannel, name="notification_channel", native_enum=False),
        nullable=False,
    )
    provider: Mapped[NotificationProvider | None] = mapped_column(
        SQLEnum(NotificationProvider, name="notification_provider", native_enum=False),
        nullable=True,
    )
    priority: Mapped[NotificationPriority] = mapped_column(
        SQLEnum(NotificationPriority, name="notification_priority", native_enum=False),
        nullable=False,
        default=NotificationPriority.NORMAL,
    )

    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    status: Mapped[NotificationStatus] = mapped_column(
        SQLEnum(NotificationStatus, name="notification_status", native_enum=False),
        nullable=False,
        default=NotificationStatus.QUEUED,
    )
    provider_response: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)

    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_notification_queue_scheduled", "scheduled_at", postgresql_where=(status == "QUEUED")),
        Index("uq_notification_idempotency", "organization_id", "idempotency_key", unique=True),
    )
