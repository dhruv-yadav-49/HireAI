import uuid
import csv
import io
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.ai_execution_trace import AIExecutionTrace
from app.models.ai_prompt_trace import AIPromptTrace
from app.models.ai_tool_trace import AIToolTrace
from app.services.execution_visualizer import ExecutionVisualizer


class TraceExporter:
    """Exports trace data in JSON, CSV, and OpenTelemetry span formats.

    ADR-016: Open Standards — OTel mapping is defined structurally even before
    a real OTel collector is wired in.
    """

    @classmethod
    async def export_json(
        cls,
        db: AsyncSession,
        ctx: RequestContext,
        execution_trace_id: uuid.UUID
    ) -> dict[str, Any]:
        """Returns the full execution timeline as a structured JSON dict."""
        return await ExecutionVisualizer.build_timeline(db, ctx, execution_trace_id)

    @classmethod
    async def export_csv(
        cls,
        db: AsyncSession,
        ctx: RequestContext,
        execution_trace_ids: list[uuid.UUID]
    ) -> str:
        """Returns CSV rows for a list of execution traces."""
        rows = []
        for eid in execution_trace_ids:
            trace = await db.get(AIExecutionTrace, eid)
            if not trace or trace.organization_id != ctx.tenant_id:
                continue
            rows.append({
                "execution_trace_id": str(trace.id),
                "trace_id": str(trace.trace_id),
                "agent_type": trace.agent_type.value,
                "status": trace.status.value,
                "started_at": trace.started_at.isoformat() if trace.started_at else "",
                "completed_at": trace.completed_at.isoformat() if trace.completed_at else "",
                "total_latency_ms": trace.total_latency_ms,
                "total_tokens": trace.total_tokens,
                "total_cost": float(trace.total_cost) if trace.total_cost else 0.0,
                "sampling_mode": trace.sampling_mode.value
            })

        if not rows:
            return "No data"

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()

    @classmethod
    async def export_otel(
        cls,
        db: AsyncSession,
        ctx: RequestContext,
        execution_trace_id: uuid.UUID
    ) -> dict[str, Any]:
        """Returns an OpenTelemetry-compatible span tree for the execution.

        ADR-016 OTel Mapping:
          AIExecutionTrace  → OTel Trace (root span)
          AIPromptTrace     → OTel child Span
          AIRetrievalTrace  → OTel child Span
          AIPlanningTrace   → OTel child Span
          AIPolicyTrace     → OTel child Span
          AIToolTrace       → OTel child Span (per tool call)
        """
        timeline = await ExecutionVisualizer.build_timeline(db, ctx, execution_trace_id)
        trace = await db.get(AIExecutionTrace, execution_trace_id)

        spans = [{
            "traceId": str(trace.trace_id),
            "spanId": str(trace.span_id),
            "parentSpanId": str(trace.parent_span_id) if trace.parent_span_id else None,
            "name": f"ai.execution.{trace.agent_type.value.lower()}",
            "kind": "SERVER",
            "startTimeUnixNano": int(trace.started_at.timestamp() * 1e9) if trace.started_at else 0,
            "endTimeUnixNano": int(trace.completed_at.timestamp() * 1e9) if trace.completed_at else 0,
            "status": {"code": "OK" if trace.status.value == "SUCCESS" else "ERROR"},
            "attributes": {
                "agent.type": trace.agent_type.value,
                "ai.total_tokens": trace.total_tokens,
                "ai.total_cost": float(trace.total_cost) if trace.total_cost else 0.0
            }
        }]

        for step in timeline["timeline"]:
            spans.append({
                "traceId": str(trace.trace_id),
                "spanId": step["span_id"],
                "parentSpanId": str(trace.span_id),
                "name": f"ai.{step['type'].lower()}.{step.get('component', 'unknown').lower()}",
                "kind": "INTERNAL",
                "attributes": {k: v for k, v in step.items() if v is not None and k not in ("span_id", "type")}
            })

        return {
            "resourceSpans": [{
                "resource": {"attributes": {"service.name": "hireai-ai-platform"}},
                "scopeSpans": [{"spans": spans}]
            }]
        }
