import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from app.models.enums import PlannerState, AIActionType, AIActionStatus, AIApprovalStatus


class SalesAIAnalyzeRequest(BaseModel):
    lead_id: uuid.UUID
    goal: Optional[str] = None


class SalesAIAnalyzeResponse(BaseModel):
    lead_id: uuid.UUID
    lead_status: str
    strategy: str
    reason: str
    recommended_action: str
    confidence: float
    retrieved_context: list[dict]


class SalesAIPlanRequest(BaseModel):
    lead_id: uuid.UUID
    goal: str
    conversation_id: Optional[uuid.UUID] = None


class SalesAIPlanResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    agent_type: str
    conversation_id: Optional[uuid.UUID]
    lead_id: Optional[uuid.UUID]
    goal: str
    plan_json: dict
    status: PlannerState
    planner_version: int
    reasoning_snapshot: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class AIActionResponse(BaseModel):
    id: uuid.UUID
    plan_id: uuid.UUID
    depends_on_action_id: Optional[uuid.UUID]
    action_type: AIActionType
    tool_name: Optional[str]
    status: AIActionStatus
    input_json: dict
    output_json: Optional[dict]
    attempt_count: int
    max_attempts: int
    last_error: Optional[str]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    duration_ms: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


class AIApprovalResponse(BaseModel):
    id: uuid.UUID
    action_id: uuid.UUID
    requested_to: Optional[uuid.UUID]
    approval_type: str
    status: AIApprovalStatus
    reason: str
    approved_at: Optional[datetime]
    rejected_at: Optional[datetime]
    comment: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class SalesAIExecuteRequest(BaseModel):
    plan_id: uuid.UUID


class SalesAIExecuteResponse(BaseModel):
    plan_id: uuid.UUID
    status: PlannerState
    actions: list[AIActionResponse]


class SalesAIApproveRequest(BaseModel):
    action_id: uuid.UUID
    comment: Optional[str] = None


class SalesAIRejectRequest(BaseModel):
    action_id: uuid.UUID
    comment: Optional[str] = None
