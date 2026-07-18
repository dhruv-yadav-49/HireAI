import uuid
from typing import Any, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.enums import AgentType, MetricType, TraceStatus
from app.models.ai_execution_trace import AIExecutionTrace
from app.models.ai_metric import AIMetric


class MetricAggregator:
    """Writes and queries flat AIMetric rows for fast per-agent/tenant analytics.

    CTO refinement #8: aggregates latency, tokens, cost, retrieval time,
    planning time, policy time, and tool time separately.
    """

    @classmethod
    async def record_metrics(
        cls,
        db: AsyncSession,
        trace: AIExecutionTrace,
        retrieval_latency_ms: Optional[int] = None,
        planning_latency_ms: Optional[int] = None,
        policy_latency_ms: Optional[int] = None,
        tool_latency_ms: Optional[int] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None
    ) -> None:
        """Writes all metric rows for one completed execution. Non-blocking."""
        try:
            rows = []

            # Total latency
            if trace.total_latency_ms is not None:
                rows.append(AIMetric(
                    execution_trace_id=trace.id,
                    organization_id=trace.organization_id,
                    agent_type=trace.agent_type,
                    metric_type=MetricType.LATENCY,
                    value_ms=trace.total_latency_ms
                ))

            # Total tokens
            if trace.total_tokens is not None:
                rows.append(AIMetric(
                    execution_trace_id=trace.id,
                    organization_id=trace.organization_id,
                    agent_type=trace.agent_type,
                    metric_type=MetricType.TOKEN,
                    value_tokens=trace.total_tokens
                ))

            # Cost
            if trace.total_cost is not None:
                rows.append(AIMetric(
                    execution_trace_id=trace.id,
                    organization_id=trace.organization_id,
                    agent_type=trace.agent_type,
                    metric_type=MetricType.COST,
                    value_cost=trace.total_cost
                ))

            # Retrieval latency
            if retrieval_latency_ms is not None:
                rows.append(AIMetric(
                    execution_trace_id=trace.id,
                    organization_id=trace.organization_id,
                    agent_type=trace.agent_type,
                    metric_type=MetricType.RETRIEVAL,
                    value_ms=retrieval_latency_ms
                ))

            # Planning latency
            if planning_latency_ms is not None:
                rows.append(AIMetric(
                    execution_trace_id=trace.id,
                    organization_id=trace.organization_id,
                    agent_type=trace.agent_type,
                    metric_type=MetricType.PLANNING,
                    value_ms=planning_latency_ms
                ))

            # Policy latency
            if policy_latency_ms is not None:
                rows.append(AIMetric(
                    execution_trace_id=trace.id,
                    organization_id=trace.organization_id,
                    agent_type=trace.agent_type,
                    metric_type=MetricType.POLICY,
                    value_ms=policy_latency_ms
                ))

            # Tool latency
            if tool_latency_ms is not None:
                rows.append(AIMetric(
                    execution_trace_id=trace.id,
                    organization_id=trace.organization_id,
                    agent_type=trace.agent_type,
                    metric_type=MetricType.TOOL,
                    value_ms=tool_latency_ms
                ))

            for row in rows:
                db.add(row)
            await db.flush()
        except Exception as e:
            print(f"[MetricAggregator] record_metrics failed (non-blocking): {e}")

    @classmethod
    async def aggregate(
        cls,
        db: AsyncSession,
        ctx: RequestContext,
        agent_type: Optional[AgentType] = None,
        period_days: int = 7
    ) -> dict:
        """Aggregates per-agent/tenant metrics over the given period."""
        from datetime import timedelta, timezone, datetime

        since = datetime.now(timezone.utc) - timedelta(days=period_days)

        # Build base execution query for this tenant
        exec_stmt = select(AIExecutionTrace.id).where(
            AIExecutionTrace.organization_id == ctx.tenant_id,
            AIExecutionTrace.started_at >= since
        )
        if agent_type:
            exec_stmt = exec_stmt.where(AIExecutionTrace.agent_type == agent_type)

        exec_result = await db.execute(exec_stmt)
        execution_ids = [r[0] for r in exec_result.fetchall()]

        if not execution_ids:
            return {
                "period_days": period_days,
                "total_executions": 0,
                "success_rate": 0.0,
                "failure_rate": 0.0,
                "avg_latency_ms": None,
                "avg_tokens": None,
                "avg_cost": None,
                "avg_retrieval_ms": None,
                "avg_planning_ms": None,
                "avg_policy_ms": None,
                "avg_tool_ms": None
            }

        # Total / status counts
        total_exec = len(execution_ids)
        status_stmt = select(
            AIExecutionTrace.status,
            func.count(AIExecutionTrace.id)
        ).where(
            AIExecutionTrace.id.in_(execution_ids)
        ).group_by(AIExecutionTrace.status)
        status_res = await db.execute(status_stmt)
        status_counts = {row[0]: row[1] for row in status_res.fetchall()}

        success = status_counts.get(TraceStatus.SUCCESS, 0)
        failed = status_counts.get(TraceStatus.FAILED, 0)

        async def _avg(metric_type: MetricType, col_name: str) -> Optional[float]:
            stmt = select(func.avg(
                AIMetric.value_ms if col_name == "ms" else
                AIMetric.value_tokens if col_name == "tokens" else
                AIMetric.value_cost
            )).where(
                AIMetric.execution_trace_id.in_(execution_ids),
                AIMetric.metric_type == metric_type
            )
            res = await db.execute(stmt)
            val = res.scalar()
            return round(float(val), 4) if val is not None else None

        return {
            "period_days": period_days,
            "agent_type": agent_type.value if agent_type else "ALL",
            "total_executions": total_exec,
            "success_count": success,
            "failure_count": failed,
            "success_rate": round(success / total_exec, 4) if total_exec else 0.0,
            "failure_rate": round(failed / total_exec, 4) if total_exec else 0.0,
            "avg_latency_ms": await _avg(MetricType.LATENCY, "ms"),
            "avg_tokens": await _avg(MetricType.TOKEN, "tokens"),
            "avg_cost": await _avg(MetricType.COST, "cost"),
            "avg_retrieval_ms": await _avg(MetricType.RETRIEVAL, "ms"),
            "avg_planning_ms": await _avg(MetricType.PLANNING, "ms"),
            "avg_policy_ms": await _avg(MetricType.POLICY, "ms"),
            "avg_tool_ms": await _avg(MetricType.TOOL, "ms")
        }
