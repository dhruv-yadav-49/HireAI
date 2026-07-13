import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.models.enums import (
    CommunicationChannel,
    CommunicationStatus,
    CommunicationPriority,
    CommunicationDirection,
    ProviderType,
    RecipientType,
    DeliveryEvent,
)


# ── Templates Schemas ──────────────────────────────────────────────────────────

class CommunicationTemplateCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    channel: CommunicationChannel
    subject_template: Optional[str] = Field(None, max_length=255)
    body_template: str = Field(..., min_length=1)
    variables_json: Optional[list[str]] = Field(default_factory=list)
    enabled: Optional[bool] = True


class CommunicationTemplateUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    subject_template: Optional[str] = Field(None, max_length=255)
    body_template: Optional[str] = None
    variables_json: Optional[list[str]] = None
    enabled: Optional[bool] = None


class CommunicationTemplateResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    channel: CommunicationChannel
    subject_template: Optional[str] = None
    body_template: str
    variables_json: list[str]
    enabled: bool
    version: int
    created_by: uuid.UUID
    updated_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CommunicationTemplateListResponse(BaseModel):
    items: list[CommunicationTemplateResponse]
    total: int


# ── Providers Schemas ──────────────────────────────────────────────────────────

class CommunicationProviderCreateRequest(BaseModel):
    provider_type: ProviderType
    channel: CommunicationChannel
    display_name: str = Field(..., min_length=1, max_length=100)
    credentials_json: dict[str, Any] = Field(default_factory=dict)
    configuration_json: dict[str, Any] = Field(default_factory=dict)
    capabilities_json: dict[str, Any] = Field(default_factory=dict)
    is_default: Optional[bool] = False
    enabled: Optional[bool] = True


class CommunicationProviderUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=100)
    credentials_json: Optional[dict[str, Any]] = None
    configuration_json: Optional[dict[str, Any]] = None
    capabilities_json: Optional[dict[str, Any]] = None
    is_default: Optional[bool] = None
    enabled: Optional[bool] = None
    health_status: Optional[str] = None


class CommunicationProviderResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    provider_type: ProviderType
    channel: CommunicationChannel
    display_name: str
    credentials_json: dict[str, Any]
    configuration_json: dict[str, Any]
    capabilities_json: dict[str, Any]
    is_default: bool
    enabled: bool
    health_status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CommunicationProviderListResponse(BaseModel):
    items: list[CommunicationProviderResponse]
    total: int


# ── Communications Schemas ─────────────────────────────────────────────────────

class CommunicationSendRequest(BaseModel):
    channel: CommunicationChannel
    recipient: str = Field(..., min_length=1, max_length=255)
    recipient_type: RecipientType = RecipientType.RAW
    
    lead_id: Optional[uuid.UUID] = None
    task_id: Optional[uuid.UUID] = None
    template_id: Optional[uuid.UUID] = None
    template_name: Optional[str] = None
    
    subject: Optional[str] = Field(None, max_length=255)
    body: Optional[str] = None
    
    attachments_json: Optional[list[dict[str, Any]]] = Field(default_factory=list)
    priority: Optional[CommunicationPriority] = CommunicationPriority.NORMAL
    direction: Optional[CommunicationDirection] = CommunicationDirection.OUTBOUND
    conversation_id: Optional[uuid.UUID] = None
    parent_communication_id: Optional[uuid.UUID] = None


class CommunicationResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    lead_id: Optional[uuid.UUID] = None
    task_id: Optional[uuid.UUID] = None
    template_id: Optional[uuid.UUID] = None
    provider_id: Optional[uuid.UUID] = None
    
    channel: CommunicationChannel
    recipient: str
    recipient_type: RecipientType
    direction: CommunicationDirection
    
    conversation_id: Optional[uuid.UUID] = None
    parent_communication_id: Optional[uuid.UUID] = None
    
    subject: Optional[str] = None
    body: str
    rendered_subject: Optional[str] = None
    rendered_body: Optional[str] = None
    template_snapshot: Optional[dict[str, Any]] = None
    attachments_json: list[dict[str, Any]]
    
    status: CommunicationStatus
    priority: CommunicationPriority
    render_engine_version: int
    idempotency_key: str
    
    scheduled_at: datetime
    sent_at: Optional[datetime] = None
    created_by: Optional[uuid.UUID] = None
    
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CommunicationListResponse(BaseModel):
    items: list[CommunicationResponse]
    total: int


# ── Delivery timeline event log Schemas ────────────────────────────────────────

class CommunicationDeliveryResponse(BaseModel):
    id: uuid.UUID
    communication_id: uuid.UUID
    event: DeliveryEvent
    sequence_no: int
    provider_message_id: Optional[str] = None
    provider_latency_ms: Optional[int] = None
    provider_status_code: Optional[int] = None
    provider_error_code: Optional[str] = None
    provider_response: dict[str, Any]
    error_message: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CommunicationDeliveryListResponse(BaseModel):
    items: list[CommunicationDeliveryResponse]
    total: int
