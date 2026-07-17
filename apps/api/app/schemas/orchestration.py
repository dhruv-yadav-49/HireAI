import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel

from app.models.enums import AgentType, AgentTaskStatus, MessageType, SessionStatus


class AIAgentDefinitionResponse(BaseModel):
    id: uuid.UUID
    agent_type: AgentType
    display_name: str
    description: str
    supported_goals: dict
    required_tools: dict
    max_parallel_tasks: int
    enabled: bool
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AIAgentSessionCreateRequest(BaseModel):
    conversation_id: Optional[uuid.UUID] = None
    initiator_agent: AgentType


class AIAgentSessionResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    conversation_id: Optional[uuid.UUID]
    initiator_agent: AgentType
    status: SessionStatus
    shared_context_json: dict
    shared_context_version: int
    shared_context_checksum: Optional[str]
    timeline_json: dict
    started_at: datetime
    completed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class AIAgentTaskCreateRequest(BaseModel):
    session_id: uuid.UUID
    assigned_agent: AgentType
    goal: str
    priority: Optional[str] = "MEDIUM"
    parent_task_id: Optional[uuid.UUID] = None


class AIAgentTaskResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    assigned_agent: AgentType
    goal: str
    status: AgentTaskStatus
    priority: str
    parent_task_id: Optional[uuid.UUID]
    result_json: Optional[dict]
    created_at: datetime

    model_config = {"from_attributes": True}


class AIAgentMessageCreateRequest(BaseModel):
    session_id: uuid.UUID
    from_agent: AgentType
    to_agent: AgentType
    message_type: MessageType
    content: str
    correlation_id: uuid.UUID
    causation_id: Optional[uuid.UUID] = None
    metadata_json: Optional[dict] = None


class AIAgentMessageResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    from_agent: AgentType
    to_agent: AgentType
    message_type: MessageType
    content: str
    correlation_id: uuid.UUID
    causation_id: Optional[uuid.UUID]
    metadata_json: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class AIAgentWorkflowResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    workflow_json: dict
    status: SessionStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class AIAgentDelegationRequest(BaseModel):
    session_id: uuid.UUID
    goal: str


class AIAgentHandoffRequest(BaseModel):
    session_id: uuid.UUID
    from_agent: AgentType
    to_agent: AgentType
    content: str
    correlation_id: uuid.UUID
    causation_id: Optional[uuid.UUID] = None
