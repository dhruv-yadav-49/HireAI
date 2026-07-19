"""
app/playground/trace_viewer.py

Trace Viewer for Developer Playground.

CTO Refinement #9: Reuses ExecutionVisualizer and ObservabilityService (Sprint 6A)
to avoid duplicate visualization logic.

ADR-023: Unified DX.
"""
import uuid
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.observability_service import ObservabilityService
from app.services.execution_visualizer import ExecutionVisualizer
from app.repositories.observability_repository import ObservabilityRepository


class TraceViewer:
    """Surfaces Sprint 6A execution traces in the Playground UI."""

    @staticmethod
    async def get_execution_trace(
        db: AsyncSession, trace_id: uuid.UUID
    ) -> Dict[str, Any]:
        repo = ObservabilityRepository(db)
        trace = await repo.get_execution(trace_id)
        if not trace:
            raise ValueError(f"Trace {trace_id} not found.")

        reasoning = await repo.get_reasoning_traces(trace_id)
        planning = await repo.get_planning_traces(trace_id)
        policies = await repo.get_policy_traces(trace_id)
        tools = await repo.get_tool_traces(trace_id)

        # Reuse ExecutionVisualizer (Sprint 6A)
        visualizer = ExecutionVisualizer()
        tree = visualizer.build_tree(
            trace=trace,
            reasoning_traces=reasoning,
            planning_traces=planning,
            policy_traces=policies,
            tool_traces=tools,
        )

        return {
            "trace_id": str(trace_id),
            "agent_type": trace.agent_type.value if trace.agent_type else "UNKNOWN",
            "status": trace.status.value if trace.status else "COMPLETED",
            "total_latency_ms": trace.total_latency_ms,
            "tree": tree,
        }
