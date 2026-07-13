import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel
from app.models.enums import (
    ConditionOperator,
    ConditionValueType,
    WorkflowActionType,
    WorkflowTriggerType,
)


class Workflow(BaseModel):
    """Workflow rule definition database model."""

    __tablename__ = "workflows"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_type: Mapped[WorkflowTriggerType] = mapped_column(
        SQLEnum(WorkflowTriggerType, name="workflow_trigger_type", native_enum=False),
        nullable=False,
    )
    
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False) # Optimistic locking

    retry_policy: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=None)
    trigger_filter: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=None)

    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    # Relationships
    conditions = relationship(
        "WorkflowCondition",
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="WorkflowCondition.order",
    )
    actions = relationship(
        "WorkflowAction",
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="WorkflowAction.order",
    )
    executions = relationship(
        "WorkflowExecution",
        back_populates="workflow",
        cascade="all, delete-orphan",
    )


class WorkflowCondition(BaseModel):
    """Workflow triggering rule conditions database model."""

    __tablename__ = "workflow_conditions"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
    )

    field: Mapped[str] = mapped_column(String(100), nullable=False)
    operator: Mapped[ConditionOperator] = mapped_column(
        SQLEnum(ConditionOperator, name="condition_operator", native_enum=False),
        nullable=False,
    )
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_type: Mapped[ConditionValueType] = mapped_column(
        SQLEnum(ConditionValueType, name="condition_value_type", native_enum=False),
        nullable=False,
        default=ConditionValueType.STRING,
    )

    group_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    logical_operator: Mapped[str] = mapped_column(String(10), default="AND", nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=1, name="order", nullable=False)

    # Relationships
    workflow = relationship("Workflow", back_populates="conditions")


class WorkflowAction(BaseModel):
    """Workflow payload action target database model."""

    __tablename__ = "workflow_actions"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
    )
    action_type: Mapped[WorkflowActionType] = mapped_column(
        SQLEnum(WorkflowActionType, name="workflow_action_type", native_enum=False),
        nullable=False,
    )
    configuration: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    retryable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(10), default="SYNC", nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=1, name="order", nullable=False)

    # Relationships
    workflow = relationship("Workflow", back_populates="actions")
