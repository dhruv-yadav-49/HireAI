import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

from app.models.enums import (
    ActorType,
    ConditionOperator,
    ConditionValueType,
    LeadPriority,
    LeadStatus,
    StepExecutionStatus,
    TaskPriority,
    TaskType,
    WorkflowActionType,
    WorkflowExecutionStatus,
    WorkflowTriggerType,
)

# ── Action Config Validator Contracts ──────────────────────────────────────────

class CreateTaskConfig(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    priority: TaskPriority = TaskPriority.LOW
    type: TaskType = TaskType.FOLLOW_UP
    offset_hours: Optional[int] = Field(None, ge=0)


class ChangeStatusConfig(BaseModel):
    status: LeadStatus


class AddTagConfig(BaseModel):
    tag_name: str = Field(..., min_length=1, max_length=100)


class AddNoteConfig(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


class UpdateLeadConfig(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    company_name: Optional[str] = Field(None, min_length=1, max_length=100)
    job_title: Optional[str] = Field(None, min_length=1, max_length=100)
    city: Optional[str] = Field(None, min_length=1, max_length=100)
    country: Optional[str] = Field(None, min_length=1, max_length=100)
    priority: Optional[LeadPriority] = None


class AssignUserConfig(BaseModel):
    assigned_to: uuid.UUID


# Mapping config validators for O(1) registry check
CONFIG_VALIDATORS: dict[WorkflowActionType, type[BaseModel]] = {
    WorkflowActionType.CREATE_TASK: CreateTaskConfig,
    WorkflowActionType.CHANGE_STATUS: ChangeStatusConfig,
    WorkflowActionType.ADD_TAG: AddTagConfig,
    WorkflowActionType.ADD_NOTE: AddNoteConfig,
    WorkflowActionType.UPDATE_LEAD: UpdateLeadConfig,
    WorkflowActionType.ASSIGN_USER: AssignUserConfig,
}

# ── Schemas ───────────────────────────────────────────────────────────────────

class WorkflowConditionSchema(BaseModel):
    field: str = Field(..., min_length=1, max_length=100)
    operator: ConditionOperator
    value: Optional[str] = None
    value_type: ConditionValueType = ConditionValueType.STRING
    group_id: Optional[str] = Field(None, max_length=50)
    logical_operator: str = Field("AND", max_length=10)
    order: int = Field(1, ge=1)

    model_config = {"from_attributes": True}


class WorkflowActionSchema(BaseModel):
    action_type: WorkflowActionType
    configuration: dict[str, Any] = Field(default_factory=dict)
    retryable: bool = True
    max_retries: int = Field(3, ge=0)
    execution_mode: str = Field("SYNC", max_length=10)
    order: int = Field(1, ge=1)

    @model_validator(mode="after")
    def validate_action_config(self) -> "WorkflowActionSchema":
        validator_class = CONFIG_VALIDATORS.get(self.action_type)
        if validator_class:
            try:
                # Enforce config schema validations
                validator_class(**self.configuration)
            except Exception as e:
                raise ValueError(f"Invalid payload config for action '{self.action_type.value}': {str(e)}")
        return self

    model_config = {"from_attributes": True}


class WorkflowCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    trigger_type: WorkflowTriggerType
    trigger_filter: Optional[dict[str, Any]] = None
    retry_policy: Optional[dict[str, Any]] = None
    conditions: list[WorkflowConditionSchema] = Field(default_factory=list)
    actions: list[WorkflowActionSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_counts(self) -> "WorkflowCreateRequest":
        if len(self.conditions) > 25:
            raise ValueError("Workflows can have a maximum of 25 conditions.")
        if len(self.actions) > 25:
            raise ValueError("Workflows can have a maximum of 25 actions.")
        return self


class WorkflowUpdateRequest(BaseModel):
    version: int = Field(..., description="Current version of the workflow for optimistic locking")
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    enabled: Optional[bool] = None
    trigger_type: Optional[WorkflowTriggerType] = None
    trigger_filter: Optional[dict[str, Any]] = None
    retry_policy: Optional[dict[str, Any]] = None
    conditions: Optional[list[WorkflowConditionSchema]] = None
    actions: Optional[list[WorkflowActionSchema]] = None

    @model_validator(mode="after")
    def validate_counts(self) -> "WorkflowUpdateRequest":
        if self.conditions is not None and len(self.conditions) > 25:
            raise ValueError("Workflows can have a maximum of 25 conditions.")
        if self.actions is not None and len(self.actions) > 25:
            raise ValueError("Workflows can have a maximum of 25 actions.")
        return self


class WorkflowResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: Optional[str] = None
    trigger_type: WorkflowTriggerType
    trigger_filter: Optional[dict[str, Any]] = None
    retry_policy: Optional[dict[str, Any]] = None
    enabled: bool
    version: int
    
    conditions: list[WorkflowConditionSchema]
    actions: list[WorkflowActionSchema]
    
    created_by: uuid.UUID
    updated_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowListResponse(BaseModel):
    items: list[WorkflowResponse]
    total: int
    page: int
    page_size: int


class WorkflowExecutionStepResponse(BaseModel):
    id: uuid.UUID
    execution_id: uuid.UUID
    step_order: int
    action_type: WorkflowActionType
    handler_name: Optional[str] = None
    status: StepExecutionStatus
    input_json: Optional[dict[str, Any]] = None
    output_json: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None

    model_config = {"from_attributes": True}


class WorkflowExecutionResponse(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    organization_id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    status: WorkflowExecutionStatus
    workflow_snapshot: dict[str, Any]
    workflow_definition_hash: str
    
    trigger_payload: dict[str, Any]
    trigger_type: WorkflowTriggerType
    trigger_source: str
    execution_mode: str
    condition_trace: Optional[dict[str, Any]] = None
    skipped_reason: Optional[str] = None
    
    steps_total: int
    steps_success: int
    steps_failed: int
    steps_skipped: int
    
    condition_duration_ms: int
    action_duration_ms: int
    duration_ms: Optional[int] = None
    
    idempotency_key: Optional[str] = None
    request_id: Optional[uuid.UUID] = None
    triggered_by: ActorType
    started_at: datetime
    finished_at: Optional[datetime] = None

    steps: list[WorkflowExecutionStepResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class WorkflowExecutionListResponse(BaseModel):
    items: list[WorkflowExecutionResponse]
    total: int
    page: int
    page_size: int
