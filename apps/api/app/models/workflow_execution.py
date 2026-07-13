import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.models.enums import (
    ActorType,
    StepExecutionStatus,
    WorkflowActionType,
    WorkflowExecutionStatus,
    WorkflowTriggerType,
)


class WorkflowExecution(Base):
    """Immutable execution logging for workflow executions."""

    __tablename__ = "workflow_executions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    status: Mapped[WorkflowExecutionStatus] = mapped_column(
        SQLEnum(WorkflowExecutionStatus, name="workflow_execution_status", native_enum=False),
        nullable=False,
        default=WorkflowExecutionStatus.RUNNING,
    )

    workflow_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    workflow_definition_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    
    trigger_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    trigger_type: Mapped[WorkflowTriggerType] = mapped_column(
        SQLEnum(WorkflowTriggerType, name="workflow_trigger_type", native_enum=False),
        nullable=False,
    )
    trigger_source: Mapped[str] = mapped_column(String(50), nullable=False, default="SYSTEM")
    execution_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="SYNC")
    condition_trace: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    skipped_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    steps_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    steps_success: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    steps_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    steps_skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    condition_duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    action_duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    request_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    triggered_by: Mapped[ActorType] = mapped_column(
        SQLEnum(ActorType, name="actor_type", native_enum=False),
        nullable=False,
        default=ActorType.SYSTEM,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    workflow = relationship("Workflow", back_populates="executions")
    steps = relationship(
        "WorkflowExecutionStep",
        back_populates="execution",
        cascade="all, delete-orphan",
        order_by="WorkflowExecutionStep.step_order",
    )


class WorkflowExecutionStep(Base):
    """Execution step detail logs."""

    __tablename__ = "workflow_execution_steps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_executions.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    action_type: Mapped[WorkflowActionType] = mapped_column(
        SQLEnum(WorkflowActionType, name="workflow_action_type", native_enum=False),
        nullable=False,
    )
    handler_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[StepExecutionStatus] = mapped_column(
        SQLEnum(StepExecutionStatus, name="step_execution_status", native_enum=False),
        nullable=False,
        default=StepExecutionStatus.SUCCESS,
    )

    input_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    output_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    execution = relationship("WorkflowExecution", back_populates="steps")
