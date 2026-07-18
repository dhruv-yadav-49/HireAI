from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

from app.models.enums import AgentType, TraceStatus, MetricType, TraceSamplingMode


# ── Execution Trace ────────────────────────────────────────────────────────────

class ExecutionTraceSummary(BaseModel):
    id: uuid.UUID
    trace_id: uuid.UUID
    agent_type: AgentType
    status: TraceStatus
    sampling_mode: TraceSamplingMode
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    total_latency_ms: Optional[int]
    total_tokens: Optional[int]
    total_cost: Optional[float]


class ExecutionTraceListResponse(BaseModel):
    items: list[ExecutionTraceSummary]
    total: int
    page: int
    page_size: int


# ── Timeline ───────────────────────────────────────────────────────────────────

class TimelineStep(BaseModel):
    step_index: int
    type: str
    component: Optional[str]
    span_id: str
    latency_ms: Optional[int] = None


class TimelineError(BaseModel):
    component: Optional[str]
    error_type: Optional[str]
    error_message: Optional[str]
    span_id: str


class ExecutionTimelineResponse(BaseModel):
    summary: dict[str, Any]
    timeline: list[dict[str, Any]]
    metrics: dict[str, Any]
    errors: list[dict[str, Any]]


# ── Metrics ────────────────────────────────────────────────────────────────────

class MetricsResponse(BaseModel):
    period_days: int
    agent_type: Optional[str]
    total_executions: int
    success_count: Optional[int] = 0
    failure_count: Optional[int] = 0
    success_rate: float
    failure_rate: float
    avg_latency_ms: Optional[float]
    avg_tokens: Optional[float]
    avg_cost: Optional[float]
    avg_retrieval_ms: Optional[float]
    avg_planning_ms: Optional[float]
    avg_policy_ms: Optional[float]
    avg_tool_ms: Optional[float]


# ── Export ─────────────────────────────────────────────────────────────────────

class ExportRequest(BaseModel):
    execution_trace_id: uuid.UUID
    format: str = Field(default="json", pattern="^(json|csv|otel)$")
