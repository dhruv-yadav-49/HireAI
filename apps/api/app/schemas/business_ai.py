import uuid
from datetime import datetime
from typing import Any, Optional, Union
from pydantic import BaseModel

from app.models.enums import BusinessReportType, ForecastPeriod, RecommendationPriority, RecommendationStatus


class AIKPIDefinitionResponse(BaseModel):
    id: uuid.UUID
    name: str
    display_name: str
    description: str
    formula: str
    unit: str
    enabled: bool
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AIKPISnapshotResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    snapshot_date: datetime
    total_leads: int
    qualified_leads: int
    won_deals: int
    lost_deals: int
    pipeline_value: float
    conversion_rate: float
    average_sales_cycle: float
    average_response_time: float
    snapshot_version: int
    calculated_at: datetime
    calculation_duration_ms: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AIForecastResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    forecast_period: ForecastPeriod
    predicted_revenue: float
    predicted_conversion_rate: float
    confidence_score: float
    forecast_model: str
    forecast_version: int
    training_period: Optional[str]
    assumptions_json: dict
    forecast_json: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class AIBusinessReportResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    report_type: BusinessReportType
    title: str
    summary: str
    report_json: dict
    parent_report_id: Optional[uuid.UUID]
    generated_by: Optional[uuid.UUID]
    generated_at: datetime

    model_config = {"from_attributes": True}


class AIRecommendationResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    recommendation_type: str
    priority: RecommendationPriority
    reason: str
    expected_impact: str
    recommended_agents: list[str]
    status: RecommendationStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class AIAnalysisRequest(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class AIAnalysisResponse(BaseModel):
    health_score: int
    health_dimensions: dict[str, int]
    health_issues: list[str]
    snapshot: AIKPISnapshotResponse
    trends: list[dict[str, Any]]
    anomalies: list[dict[str, Any]]
    recommendations: list[AIRecommendationResponse]


class AIReportRequest(BaseModel):
    report_type: BusinessReportType
    title: str
    parent_report_id: Optional[uuid.UUID] = None


class AIForecastRequest(BaseModel):
    forecast_period: ForecastPeriod
