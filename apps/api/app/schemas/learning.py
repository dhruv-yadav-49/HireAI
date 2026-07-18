from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

from app.models.enums import (
    LearningStatus,
    ImprovementType,
    SuggestionStatus
)


# ── Run request/response ────────────────────────────────────────────────────────

class DatasetSummaryResponse(BaseModel):
    id: uuid.UUID
    execution_trace_id: Optional[uuid.UUID]
    evaluation_id: Optional[uuid.UUID]
    feedback_id: Optional[uuid.UUID]
    agent_type: str
    input_json: dict[str, Any]
    output_json: dict[str, Any]
    expected_output: Optional[str]
    quality_score: Optional[float]
    dataset_version: int
    dataset_source: str
    created_at: datetime


class DatasetListResponse(BaseModel):
    items: list[DatasetSummaryResponse]
    total: int
    page: int
    page_size: int


# ── Improvement / Suggestion ───────────────────────────────────────────────────

class ImprovementSummaryResponse(BaseModel):
    id: uuid.UUID
    improvement_type: ImprovementType
    current_version: str
    proposed_version: str
    reason: str
    pattern_confidence: float
    deployment_confidence: float
    status: SuggestionStatus
    supporting_evaluation_ids: Optional[dict[str, Any]]
    supporting_feedback_ids: Optional[dict[str, Any]]
    supporting_trace_ids: Optional[dict[str, Any]]
    created_at: datetime


class ImprovementListResponse(BaseModel):
    items: list[ImprovementSummaryResponse]
    total: int
    page: int
    page_size: int


# ── Suggestion Approval ────────────────────────────────────────────────────────

class SuggestionActionRequest(BaseModel):
    suggestion_id: uuid.UUID
    suggestion_type: str = Field(default="prompt", pattern="^(prompt|policy)$")
