import uuid
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.enums import AgentType, TraceStatus
from app.models.ai_execution_trace import AIExecutionTrace
from app.models.ai_prompt_trace import AIPromptTrace
from app.models.ai_retrieval_trace import AIRetrievalTrace
from app.models.ai_reasoning_trace import AIReasoningTrace
from app.models.ai_planning_trace import AIPlanningTrace
from app.models.ai_policy_trace import AIPolicyTrace
from app.models.ai_tool_trace import AIToolTrace
from app.models.ai_metric import AIMetric


class ObservabilityRepository:
    """Multi-tenant safe database queries for all observability trace tables."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_executions(
        self,
        ctx: RequestContext,
        agent_type: Optional[AgentType] = None,
        status: Optional[TraceStatus] = None,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[list[AIExecutionTrace], int]:
        stmt = select(AIExecutionTrace).where(
            AIExecutionTrace.organization_id == ctx.tenant_id
        )
        if agent_type:
            stmt = stmt.where(AIExecutionTrace.agent_type == agent_type)
        if status:
            stmt = stmt.where(AIExecutionTrace.status == status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_res = await self.db.execute(count_stmt)
        total = count_res.scalar() or 0

        stmt = stmt.order_by(AIExecutionTrace.started_at.desc())
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def get_execution(
        self,
        ctx: RequestContext,
        execution_trace_id: uuid.UUID
    ) -> Optional[AIExecutionTrace]:
        result = await self.db.execute(
            select(AIExecutionTrace).where(
                AIExecutionTrace.id == execution_trace_id,
                AIExecutionTrace.organization_id == ctx.tenant_id
            )
        )
        return result.scalar_one_or_none()

    async def get_all_spans(
        self,
        ctx: RequestContext,
        execution_trace_id: uuid.UUID
    ) -> dict:
        """Fetches all child spans for one execution in one query per table."""
        trace = await self.get_execution(ctx, execution_trace_id)
        if not trace:
            return {}

        async def fetch(model, id_col):
            res = await self.db.execute(
                select(model).where(id_col == execution_trace_id).order_by(model.step_index)
            )
            return res.scalars().all()

        return {
            "prompts": await fetch(AIPromptTrace, AIPromptTrace.execution_trace_id),
            "retrievals": await fetch(AIRetrievalTrace, AIRetrievalTrace.execution_trace_id),
            "reasonings": await fetch(AIReasoningTrace, AIReasoningTrace.execution_trace_id),
            "plannings": await fetch(AIPlanningTrace, AIPlanningTrace.execution_trace_id),
            "policies": await fetch(AIPolicyTrace, AIPolicyTrace.execution_trace_id),
            "tools": await fetch(AIToolTrace, AIToolTrace.execution_trace_id)
        }

    async def list_metrics(
        self,
        ctx: RequestContext,
        execution_trace_id: uuid.UUID
    ) -> list[AIMetric]:
        result = await self.db.execute(
            select(AIMetric).where(
                AIMetric.execution_trace_id == execution_trace_id,
                AIMetric.organization_id == ctx.tenant_id
            )
        )
        return list(result.scalars().all())
