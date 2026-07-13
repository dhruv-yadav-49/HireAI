import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

from app.models.enums import AIProvider, MessageRole, ConversationStatus, ToolExecutionStatus, AIRuntimeState


# ── AI Provider Config Schemas ───────────────────────────────────────────────

class AIProviderConfigCreateRequest(BaseModel):
    provider: AIProvider
    display_name: str = Field(min_length=1, max_length=100)
    credentials_json: dict = Field(default_factory=dict)
    configuration_json: dict = Field(default_factory=dict)
    is_default: bool = False
    enabled: bool = True


class AIProviderConfigUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    credentials_json: Optional[dict] = None
    configuration_json: Optional[dict] = None
    is_default: Optional[bool] = None
    enabled: Optional[bool] = None


class AIProviderConfigResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    provider: AIProvider
    display_name: str
    configuration_json: dict
    is_default: bool
    enabled: bool
    health_status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── AI Prompt Schemas ──────────────────────────────────────────────────────────

class AIPromptCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    prompt_type: str = Field(min_length=1, max_length=50)
    content: str = Field(min_length=1)
    variables_json: list[str] = Field(default_factory=list)
    enabled: bool = True


class AIPromptUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    prompt_type: Optional[str] = Field(default=None, min_length=1, max_length=50)
    content: Optional[str] = None
    variables_json: Optional[list[str]] = None
    enabled: Optional[bool] = None


class AIPromptResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    prompt_type: str
    content: str
    variables_json: list[str]
    version: int
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── AI Agent Schemas ──────────────────────────────────────────────────────────

class AIAgentCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None
    role: str = Field(min_length=1, max_length=50)
    system_prompt: str = Field(min_length=1)
    default_prompt_id: Optional[uuid.UUID] = None
    provider_config_id: Optional[uuid.UUID] = None
    provider: AIProvider
    model: str = Field(min_length=1, max_length=100)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=1)
    supports_tools: bool = True
    supports_streaming: bool = True
    supports_memory: bool = True
    enabled: bool = True


class AIAgentUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    role: Optional[str] = Field(default=None, min_length=1, max_length=50)
    system_prompt: Optional[str] = None
    default_prompt_id: Optional[uuid.UUID] = None
    provider_config_id: Optional[uuid.UUID] = None
    provider: Optional[AIProvider] = None
    model: Optional[str] = Field(default=None, min_length=1, max_length=100)
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    supports_tools: Optional[bool] = None
    supports_streaming: Optional[bool] = None
    supports_memory: Optional[bool] = None
    enabled: Optional[bool] = None


class AIAgentResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: Optional[str]
    role: str
    system_prompt: str
    default_prompt_id: Optional[uuid.UUID]
    provider_config_id: Optional[uuid.UUID]
    provider: AIProvider
    model: str
    temperature: float
    max_tokens: int
    supports_tools: bool
    supports_streaming: bool
    supports_memory: bool
    enabled: bool
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── AI Conversation & Execution Schemas ──────────────────────────────────────

class AIConversationResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    agent_id: uuid.UUID
    lead_id: Optional[uuid.UUID]
    user_id: Optional[uuid.UUID]
    status: ConversationStatus
    runtime_state: AIRuntimeState
    agent_snapshot: Optional[dict] = None
    agent_version: Optional[int]
    provider: Optional[AIProvider]
    model: Optional[str]
    temperature: Optional[float]
    max_tokens: Optional[int]
    conversation_summary: Optional[str]
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: float
    total_latency_ms: int
    tool_calls_count: int
    started_at: datetime
    ended_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class AIMessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: MessageRole
    content: str
    message_index: int
    token_count: int
    latency_ms: int
    response_time_ms: int
    finish_reason: Optional[str]
    cached: bool
    provider: AIProvider
    model: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AIToolExecutionResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    tool_name: str
    handler_name: str
    tool_version: str
    request_id: Optional[uuid.UUID]
    input_json: dict
    output_json: dict
    started_at: datetime
    finished_at: Optional[datetime]
    duration_ms: int
    status: ToolExecutionStatus
    retry_count: int
    attempt: int
    error_message: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class AIChatRequest(BaseModel):
    agent_id: uuid.UUID
    message: str = Field(min_length=1)
    conversation_id: Optional[uuid.UUID] = None
    lead_id: Optional[uuid.UUID] = None
    user_id: Optional[uuid.UUID] = None


class AIChatResponse(BaseModel):
    conversation_id: uuid.UUID
    agent_id: uuid.UUID
    status: ConversationStatus
    runtime_state: AIRuntimeState
    message: AIMessageResponse
    tool_executions: list[AIToolExecutionResponse] = Field(default_factory=list)
