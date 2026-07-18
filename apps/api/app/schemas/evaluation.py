from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

from app.models.enums import (
    EvaluationStatus,
    EvaluationMetric,
    QualityGrade,
    FeedbackType,
    FeedbackCategory,
    QualityRuleAction
)


# ── Run request/response ────────────────────────────────────────────────────────

class EvaluationRunRequest(BaseModel):
    execution_trace_id: uuid.UUID


class EvaluationSummaryResponse(BaseModel):
    id: uuid.UUID
    execution_trace_id: uuid.UUID
    agent_type: str
    status: EvaluationStatus
    overall_score: Optional[float]
    quality_grade: Optional[QualityGrade]
    summary: Optional[str]
    evaluation_version: int
    eligible_for_training: bool
    created_at: datetime


class EvaluationListResponse(BaseModel):
    items: list[EvaluationSummaryResponse]
    total: int
    page: int
    page_size: int


# ── Detail response ────────────────────────────────────────────────────────────

class MetricDetail(BaseModel):
    metric_type: EvaluationMetric
    score: float
    weight: float
    details: dict[str, Any]


class EvaluationDetailResponse(BaseModel):
    summary: dict[str, Any]
    metrics: list[MetricDetail]


# ── Feedback ───────────────────────────────────────────────────────────────────

class FeedbackCreateRequest(BaseModel):
    evaluation_id: uuid.UUID
    feedback_type: FeedbackType
    feedback_category: FeedbackCategory = FeedbackCategory.OTHER
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    comment: Optional[str] = None


class FeedbackResponse(BaseModel):
    id: uuid.UUID
    evaluation_id: uuid.UUID
    user_id: Optional[uuid.UUID]
    feedback_type: FeedbackType
    feedback_category: FeedbackCategory
    rating: Optional[int]
    comment: Optional[str]
    created_at: datetime


# ── Quality Rules ──────────────────────────────────────────────────────────────

class QualityRuleResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    rule_name: str
    metric_type: EvaluationMetric
    threshold: float
    action: QualityRuleAction
    enabled: bool
    created_at: datetime
