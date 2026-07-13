import uuid
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.workflow_execution import WorkflowExecution, WorkflowExecutionStep
from app.models.enums import WorkflowExecutionStatus


class WorkflowExecutionRepository:
    """Persistence only for WorkflowExecutions and Steps. Scoped strictly to tenant."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_execution(self, execution: WorkflowExecution) -> WorkflowExecution:
        self.db.add(execution)
        await self.db.flush()
        return execution

    async def get_execution_by_id(
        self, ctx: RequestContext, execution_id: uuid.UUID
    ) -> WorkflowExecution | None:
        stmt = (
            select(WorkflowExecution)
            .options(selectinload(WorkflowExecution.steps))
            .where(
                WorkflowExecution.id == execution_id,
                WorkflowExecution.organization_id == ctx.tenant_id,
            )
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_executions(
        self,
        ctx: RequestContext,
        workflow_id: Optional[uuid.UUID] = None,
        status: Optional[WorkflowExecutionStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[WorkflowExecution], int]:
        stmt = (
            select(WorkflowExecution)
            .options(selectinload(WorkflowExecution.steps))
            .where(WorkflowExecution.organization_id == ctx.tenant_id)
        )

        if workflow_id is not None:
            stmt = stmt.where(WorkflowExecution.workflow_id == workflow_id)
        if status is not None:
            stmt = stmt.where(WorkflowExecution.status == status)

        # Count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # Sort and paginate
        stmt = stmt.order_by(WorkflowExecution.started_at.desc())
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)

        result = await self.db.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def create_execution_step(
        self, step: WorkflowExecutionStep
    ) -> WorkflowExecutionStep:
        self.db.add(step)
        await self.db.flush()
        return step

    async def check_duplicate_execution(
        self, tenant_id: uuid.UUID, idempotency_key: str
    ) -> WorkflowExecution | None:
        """Finds any non-failed execution matching tenant and idempotency key."""
        stmt = select(WorkflowExecution).where(
            WorkflowExecution.organization_id == tenant_id,
            WorkflowExecution.idempotency_key == idempotency_key,
            WorkflowExecution.status.in_([WorkflowExecutionStatus.SUCCESS, WorkflowExecutionStatus.RUNNING]),
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()
