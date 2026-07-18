import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_context
from app.core.context import RequestContext
from app.db.session import get_db
from app.models.enums import AgentType, TraceStatus
from app.schemas.observability import (
    ExecutionTraceListResponse,
    ExecutionTimelineResponse,
    MetricsResponse,
    ExportRequest
)
from app.services.observability_service import ObservabilityService

router = APIRouter(prefix="/observability", tags=["Observability"])


@router.get("/executions", summary="List AI execution traces")
async def list_executions(
    agent_type: Optional[AgentType] = Query(default=None),
    status: Optional[TraceStatus] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
) -> dict:
    svc = ObservabilityService(db)
    return await svc.list_executions(ctx, agent_type=agent_type, status=status, page=page, page_size=page_size)


@router.get("/executions/{execution_trace_id}", summary="Get full execution timeline")
async def get_execution_detail(
    execution_trace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
) -> dict:
    """Returns LangSmith-style trace: summary, ordered timeline, metrics, errors."""
    svc = ObservabilityService(db)
    return await svc.get_execution_detail(ctx, execution_trace_id)


@router.get("/metrics", summary="Get aggregated AI performance metrics")
async def get_metrics(
    agent_type: Optional[AgentType] = Query(default=None),
    period_days: int = Query(default=7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
) -> dict:
    """Returns avg latency, tokens, cost, retrieval time, planning time, policy time, tool time."""
    svc = ObservabilityService(db)
    return await svc.get_metrics(ctx, agent_type=agent_type, period_days=period_days)


@router.get("/traces", summary="Get all child spans for an execution")
async def get_traces(
    execution_trace_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
) -> dict:
    svc = ObservabilityService(db)
    return await svc.get_traces(ctx, execution_trace_id)


@router.post("/export", summary="Export trace as JSON, CSV, or OpenTelemetry")
async def export_trace(
    body: ExportRequest,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    """Exports trace data. format: 'json' | 'csv' | 'otel'"""
    svc = ObservabilityService(db)
    result = await svc.export(ctx, body.execution_trace_id, body.format)
    if body.format == "csv":
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(result, media_type="text/csv")
    return result
