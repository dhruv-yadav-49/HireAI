import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel

from app.models.enums import (
    CampaignType,
    CampaignGoal,
    CampaignStatus,
    CampaignPriority,
    AudienceType,
    ContentType,
    ABTestStatus
)


class AICampaignResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    campaign_type: CampaignType
    campaign_goal: CampaignGoal
    status: CampaignStatus
    priority: CampaignPriority
    strategy_json: dict
    campaign_version: int
    parent_campaign_id: Optional[uuid.UUID]
    created_by: Optional[uuid.UUID]
    created_at: datetime

    model_config = {"from_attributes": True}


class AIAudienceSegmentResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    segment_type: AudienceType
    criteria_json: dict
    estimated_size: int
    segment_version: int
    generated_by: Optional[uuid.UUID]
    generated_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class AIMarketingContentResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    campaign_id: uuid.UUID
    content_type: ContentType
    subject: Optional[str]
    body: str
    variables_json: dict
    version: int
    parent_content_id: Optional[uuid.UUID]
    generation_prompt: Optional[str]
    approval_id: Optional[uuid.UUID]
    created_at: datetime

    model_config = {"from_attributes": True}


class AIABTestResponse(BaseModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    variants_json: dict
    winner: Optional[str]
    winner_metrics: dict
    metrics_json: dict
    status: ABTestStatus

    model_config = {"from_attributes": True}


class AICampaignExecutionResponse(BaseModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    segment_id: Optional[uuid.UUID]
    scheduled_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    status: CampaignStatus
    audience_snapshot_json: dict
    statistics_json: dict
    attribution_model: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AICampaignCreateRequest(BaseModel):
    name: str
    campaign_type: CampaignType
    campaign_goal: CampaignGoal
    priority: CampaignPriority = CampaignPriority.MEDIUM
    strategy_json: Optional[dict] = None
    parent_campaign_id: Optional[uuid.UUID] = None


class AIAudienceSegmentRequest(BaseModel):
    name: str
    segment_type: AudienceType
    criteria_json: dict


class AIMarketingContentRequest(BaseModel):
    campaign_id: uuid.UUID
    content_type: ContentType
    subject: Optional[str] = None
    body: str
    variables_json: Optional[dict] = None
    parent_content_id: Optional[uuid.UUID] = None
    generation_prompt: Optional[str] = None


class AIABTestRequest(BaseModel):
    campaign_id: uuid.UUID
    variants_json: dict


class AICampaignExecutionRequest(BaseModel):
    campaign_id: uuid.UUID
    segment_id: Optional[uuid.UUID] = None
    scheduled_at: Optional[datetime] = None
    attribution_model: str = "LAST_TOUCH"
