import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.workflow import Workflow, WorkflowCondition, WorkflowAction
from app.models.enums import WorkflowTriggerType


class WorkflowRepository:
    """Persistence only for Workflows. Enforces tenant boundaries strictly
    via ctx.tenant_id. No role or permission checks.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, workflow: Workflow) -> Workflow:
        self.db.add(workflow)
        await self.db.flush()
        return workflow

    async def get_by_id(self, ctx: RequestContext, workflow_id: uuid.UUID) -> Workflow | None:
        """Finds non-deleted workflow matching ID and tenant ID."""
        result = await self.db.execute(
            select(Workflow)
            .options(selectinload(Workflow.conditions), selectinload(Workflow.actions))
            .where(
                Workflow.id == workflow_id,
                Workflow.organization_id == ctx.tenant_id,
                Workflow.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_workflows(
        self,
        ctx: RequestContext,
        trigger_type: WorkflowTriggerType | None = None,
        enabled: bool | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Workflow], int]:
        """List non-deleted workflows with filters, search, and pagination."""
        stmt = select(Workflow).options(
            selectinload(Workflow.conditions), selectinload(Workflow.actions)
        ).where(
            Workflow.organization_id == ctx.tenant_id,
            Workflow.deleted_at.is_(None),
        )

        if trigger_type is not None:
            stmt = stmt.where(Workflow.trigger_type == trigger_type)
        if enabled is not None:
            stmt = stmt.where(Workflow.enabled == enabled)

        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Workflow.name.ilike(search_pattern),
                    Workflow.description.ilike(search_pattern),
                )
            )

        # Count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # Sort and paginate
        stmt = stmt.order_by(Workflow.created_at.desc())
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)

        result = await self.db.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def get_enabled_by_trigger(
        self, tenant_id: uuid.UUID, trigger_type: WorkflowTriggerType
    ) -> list[Workflow]:
        """Fetch all enabled workflows matching a specific trigger type for a tenant.
        This is used for automatic event triggers, loading related conditions and actions.
        """
        stmt = (
            select(Workflow)
            .options(selectinload(Workflow.conditions), selectinload(Workflow.actions))
            .where(
                Workflow.organization_id == tenant_id,
                Workflow.trigger_type == trigger_type,
                Workflow.enabled.is_(True),
                Workflow.deleted_at.is_(None),
            )
            .order_by(Workflow.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update(self, workflow: Workflow) -> Workflow:
        self.db.add(workflow)
        await self.db.flush()
        return workflow

    async def soft_delete(self, ctx: RequestContext, workflow_id: uuid.UUID) -> bool:
        workflow = await self.get_by_id(ctx, workflow_id)
        if workflow is None:
            return False
        workflow.deleted_at = datetime.now(timezone.utc)
        self.db.add(workflow)
        await self.db.flush()
        return True
