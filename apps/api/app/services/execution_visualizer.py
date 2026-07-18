import uuid
from typing import Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.ai_execution_trace import AIExecutionTrace
from app.models.ai_prompt_trace import AIPromptTrace
from app.models.ai_retrieval_trace import AIRetrievalTrace
from app.models.ai_reasoning_trace import AIReasoningTrace
from app.models.ai_planning_trace import AIPlanningTrace
from app.models.ai_policy_trace import AIPolicyTrace
from app.models.ai_tool_trace import AIToolTrace
from app.models.enums import TraceStatus


class ExecutionVisualizer:
    """Reconstructs the full execution timeline from all child trace spans.

    CTO refinement #11: Returns structured {summary, timeline, metrics, errors}.
    Timeline is ordered by step_index for deterministic reconstruction (not timestamps).
    """

    @classmethod
    async def build_timeline(
        cls,
        db: AsyncSession,
        ctx: RequestContext,
        execution_trace_id: uuid.UUID
    ) -> dict[str, Any]:
        """Builds the full LangSmith-style execution timeline for one trace."""

        # Fetch root trace (tenant-isolated)
        trace = await db.get(AIExecutionTrace, execution_trace_id)
        if not trace or trace.organization_id != ctx.tenant_id:
            raise ValueError("Execution trace not found or unauthorized.")

        # Fetch all child spans
        prompt_res = await db.execute(
            select(AIPromptTrace)
            .where(AIPromptTrace.execution_trace_id == execution_trace_id)
            .order_by(AIPromptTrace.step_index)
        )
        prompts = prompt_res.scalars().all()

        retrieval_res = await db.execute(
            select(AIRetrievalTrace)
            .where(AIRetrievalTrace.execution_trace_id == execution_trace_id)
            .order_by(AIRetrievalTrace.step_index)
        )
        retrievals = retrieval_res.scalars().all()

        reasoning_res = await db.execute(
            select(AIReasoningTrace)
            .where(AIReasoningTrace.execution_trace_id == execution_trace_id)
            .order_by(AIReasoningTrace.step_index)
        )
        reasonings = reasoning_res.scalars().all()

        planning_res = await db.execute(
            select(AIPlanningTrace)
            .where(AIPlanningTrace.execution_trace_id == execution_trace_id)
            .order_by(AIPlanningTrace.step_index)
        )
        plannings = planning_res.scalars().all()

        policy_res = await db.execute(
            select(AIPolicyTrace)
            .where(AIPolicyTrace.execution_trace_id == execution_trace_id)
            .order_by(AIPolicyTrace.step_index)
        )
        policies = policy_res.scalars().all()

        tool_res = await db.execute(
            select(AIToolTrace)
            .where(AIToolTrace.execution_trace_id == execution_trace_id)
            .order_by(AIToolTrace.step_index)
        )
        tools = tool_res.scalars().all()

        # Build ordered timeline list
        timeline = []

        for p in prompts:
            timeline.append({
                "step_index": p.step_index,
                "type": "PROMPT",
                "component": p.component,
                "span_id": str(p.span_id),
                "latency_ms": p.latency_ms,
                "prompt_hash": p.prompt_hash,
                "prompt_tokens": p.prompt_tokens,
                "completion_tokens": p.completion_tokens
            })

        for r in retrievals:
            timeline.append({
                "step_index": r.step_index,
                "type": "RETRIEVAL",
                "component": r.component,
                "span_id": str(r.span_id),
                "query": r.query,
                "vector_hit_count": r.vector_hit_count,
                "memory_latency_ms": r.memory_latency_ms,
                "crm_latency_ms": r.crm_latency_ms,
                "knowledge_latency_ms": r.knowledge_latency_ms,
                "vector_search_latency_ms": r.vector_search_latency_ms,
                "total_latency_ms": r.total_retrieval_latency_ms
            })

        for rs in reasonings:
            timeline.append({
                "step_index": rs.step_index,
                "type": "REASONING",
                "component": rs.component,
                "span_id": str(rs.span_id),
                "reason": rs.reason,
                "confidence": rs.confidence,
                "priority": rs.priority,
                "risk": rs.risk
            })

        for pl in plannings:
            timeline.append({
                "step_index": pl.step_index,
                "type": "PLANNING",
                "component": pl.component,
                "span_id": str(pl.span_id),
                "goal": pl.goal,
                "planner_version": pl.planner_version,
                "latency_ms": pl.latency_ms,
                "planning_tokens": pl.planning_tokens
            })

        for po in policies:
            timeline.append({
                "step_index": po.step_index,
                "type": "POLICY",
                "component": po.component,
                "span_id": str(po.span_id),
                "policy": po.policy,
                "decision": po.decision,
                "risk": po.risk,
                "reason": po.reason,
                "latency_ms": po.latency_ms
            })

        for t in tools:
            timeline.append({
                "step_index": t.step_index,
                "type": "TOOL",
                "component": t.component or t.tool_name,
                "span_id": str(t.span_id),
                "tool_name": t.tool_name,
                "duration_ms": t.duration_ms,
                "retries": t.retries,
                "status": t.status.value
            })

        # Sort by step_index for deterministic order (CTO refinement #5)
        timeline.sort(key=lambda x: x["step_index"])

        # Collect errors from all spans
        errors = []
        for item in [trace] + list(prompts) + list(retrievals) + list(reasonings) + list(plannings) + list(policies) + list(tools):
            err_type = getattr(item, "error_type", None)
            err_msg = getattr(item, "error_message", None)
            if err_type or err_msg:
                errors.append({
                    "component": getattr(item, "component", "Unknown"),
                    "error_type": err_type,
                    "error_message": err_msg,
                    "span_id": str(getattr(item, "span_id", ""))
                })

        return {
            "summary": {
                "execution_trace_id": str(trace.id),
                "trace_id": str(trace.trace_id),
                "agent_type": trace.agent_type.value,
                "status": trace.status.value,
                "sampling_mode": trace.sampling_mode.value,
                "started_at": trace.started_at.isoformat() if trace.started_at else None,
                "completed_at": trace.completed_at.isoformat() if trace.completed_at else None,
                "total_latency_ms": trace.total_latency_ms,
                "total_tokens": trace.total_tokens,
                "total_cost": float(trace.total_cost) if trace.total_cost else None
            },
            "timeline": timeline,
            "metrics": {
                "total_spans": len(timeline),
                "prompt_spans": len(prompts),
                "retrieval_spans": len(retrievals),
                "reasoning_spans": len(reasonings),
                "planning_spans": len(plannings),
                "policy_spans": len(policies),
                "tool_spans": len(tools)
            },
            "errors": errors
        }
