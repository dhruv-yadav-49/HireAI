import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

from app.models.enums import ActorType, TaskActivityType, TaskPriority, TaskStatus, TaskType


class TaskCreateRequest(BaseModel):
    lead_id: uuid.UUID
    assigned_to: Optional[uuid.UUID] = None
    
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    
    priority: TaskPriority = TaskPriority.LOW
    type: TaskType = TaskType.FOLLOW_UP
    
    due_at: Optional[datetime] = None
    reminder_at: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_dates(self) -> "TaskCreateRequest":
        now = datetime.now(timezone.utc)
        if self.due_at and self.due_at < now:
            raise ValueError("due_at cannot be in the past.")
        if self.reminder_at and not self.due_at:
            raise ValueError("due_at is required when reminder_at is provided.")
        if self.reminder_at and self.due_at and self.reminder_at >= self.due_at:
            raise ValueError("reminder_at must be before due_at.")
        return self


class TaskUpdateRequest(BaseModel):
    """Update schema. Enforces optimistic lock version parameter."""
    version: int = Field(..., description="Current version of the task for optimistic locking")
    
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    type: Optional[TaskType] = None
    
    due_at: Optional[datetime] = None
    reminder_at: Optional[datetime] = None
    assigned_to: Optional[uuid.UUID] = None

    @model_validator(mode="after")
    def validate_dates(self) -> "TaskUpdateRequest":
        if self.reminder_at and self.due_at and self.reminder_at >= self.due_at:
            raise ValueError("reminder_at must be before due_at.")
        return self


class TaskResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    lead_id: uuid.UUID
    created_by: uuid.UUID
    updated_by: uuid.UUID
    assigned_to: Optional[uuid.UUID] = None

    title: str
    description: Optional[str] = None
    
    status: TaskStatus
    priority: TaskPriority
    type: TaskType
    
    version: int
    is_overdue: bool = False

    due_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    reminder_at: Optional[datetime] = None
    
    last_activity_at: datetime
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def compute_overdue(self) -> "TaskResponse":
        if self.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            if self.due_at and self.due_at < datetime.now(timezone.utc):
                self.is_overdue = True
        return self

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int
    page: int
    page_size: int


class TaskActivityResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    actor_id: Optional[uuid.UUID] = None
    actor_type: ActorType
    activity_type: TaskActivityType
    metadata: dict[str, Any] = Field(validation_alias="event_metadata")
    metadata_version: int
    created_at: datetime

    model_config = {"from_attributes": True}
