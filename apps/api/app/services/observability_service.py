import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.events import DomainEvent, get_event_publisher
from app.models.enums import AgentType, TraceStatus
from app.repositories.observability_repository import ObservabilityRepository
from app.services.execution_visualizer import ExecutionVisualizer
from app.services.metric_aggregator import MetricAggregator
from app.services.trace_exporter import TraceExporter


class ObservabilityService:
    """Orchestrates all observability operations. Entry point for the REST layer.

    ADR-016: Passive — never affects AI execution.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ObservabilityRepository(db)

    async def _publish(self, ctx: RequestContext, event_name: str, payload: dict) -> None:
        event = DomainEvent(
            event_name=event_name,
            tenant_id=ctx.tenant_id,
            request_id=ctx.request_id,
            actor_id=ctx.user.id if ctx.user else None,
            payload=payload
        )
        pub = get_event_publisher()
        await pub.publish(event)

    async def list_executions(
        self,
        ctx: RequestContext,
        agent_type: Optional[AgentType] = None,
        status: Optional[TraceStatus] = None,
        page: int = 1,
        page_size: int = 20
    ) -> dict:
        items, total = await self.repo.list_executions(ctx, agent_type, status, page, page_size)
        return {
            "items": [
                {
                    "id": str(t.id),
                    "trace_id": str(t.trace_id),
                    "agent_type": t.agent_type.value,
                    "status": t.status.value,
                    "sampling_mode": t.sampling_mode.value,
                    "started_at": t.started_at.isoformat() if t.started_at else None,
                    "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                    "total_latency_ms": t.total_latency_ms,
                    "total_tokens": t.total_tokens,
                    "total_cost": float(t.total_cost) if t.total_cost else None
                }
                for t in items
            ],
            "total": total,
            "page": page,
            "page_size": page_size
        }

    async def get_execution_detail(
        self,
        ctx: RequestContext,
        execution_trace_id: uuid.UUID
    ) -> dict:
        """Returns full LangSmith-style timeline for one execution."""
        return await ExecutionVisualizer.build_timeline(self.db, ctx, execution_trace_id)

    async def get_metrics(
        self,
        ctx: RequestContext,
        agent_type: Optional[AgentType] = None,
        period_days: int = 7
    ) -> dict:
        return await MetricAggregator.aggregate(self.db, ctx, agent_type, period_days)

    async def get_traces(
        self,
        ctx: RequestContext,
        execution_trace_id: uuid.UUID
    ) -> dict:
        """Returns all child spans for one execution."""
        spans = await self.repo.get_all_spans(ctx, execution_trace_id)
        return {
            "execution_trace_id": str(execution_trace_id),
            "span_counts": {k: len(v) for k, v in spans.items()},
            "spans": {
                k: [{"id": str(s.id), "step_index": s.step_index, "component": getattr(s, "component", None)}
                    for s in v]
                for k, v in spans.items()
            }
        }

    async def export(
        self,
        ctx: RequestContext,
        execution_trace_id: uuid.UUID,
        format: str = "json"
    ) -> dict | str:
        """Exports a trace in JSON, CSV, or OpenTelemetry format."""
        result: dict | str
        if format == "csv":
            result = await TraceExporter.export_csv(self.db, ctx, [execution_trace_id])
        elif format == "otel":
            result = await TraceExporter.export_otel(self.db, ctx, execution_trace_id)
        else:
            result = await TraceExporter.export_json(self.db, ctx, execution_trace_id)

        await self._publish(ctx, "trace.exported", {
            "execution_trace_id": str(execution_trace_id),
            "format": format
        })
        return result
