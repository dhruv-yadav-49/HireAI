import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.task import Task


class TaskRepository:
    """Persistence only for Task model. Enforces tenant boundaries strictly
    via ctx.tenant_id. No role or permission checks.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, task: Task) -> Task:
        self.db.add(task)
        await self.db.flush()
        return task

    async def get_by_id(self, ctx: RequestContext, task_id: uuid.UUID) -> Task | None:
        """Finds non-deleted task matching ID and tenant ID."""
        result = await self.db.execute(
            select(Task).where(
                Task.id == task_id,
                Task.organization_id == ctx.tenant_id,
                Task.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        ctx: RequestContext,
        status: str | None = None,
        priority: str | None = None,
        type_: str | None = None,
        lead_id: uuid.UUID | None = None,
        assigned_to: uuid.UUID | None = None,
        due_before: datetime | None = None,
        due_after: datetime | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> tuple[list[Task], int]:
        """List non-deleted tasks with filters, search, pagination, and sorting."""
        # 1. Base Query
        stmt = select(Task).where(
            Task.organization_id == ctx.tenant_id,
            Task.deleted_at.is_(None),
        )

        # 2. Filters
        if status is not None:
            stmt = stmt.where(Task.status == status)
        if priority is not None:
            stmt = stmt.where(Task.priority == priority)
        if type_ is not None:
            stmt = stmt.where(Task.type == type_)
        if lead_id is not None:
            stmt = stmt.where(Task.lead_id == lead_id)
        if assigned_to is not None:
            stmt = stmt.where(Task.assigned_to == assigned_to)
        if due_before is not None:
            stmt = stmt.where(Task.due_at <= due_before)
        if due_after is not None:
            stmt = stmt.where(Task.due_at >= due_after)

        # 3. Search
        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Task.title.ilike(search_pattern),
                    Task.description.ilike(search_pattern),
                )
            )

        # 4. Count query
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # 5. Sorting
        sort_column = Task.created_at
        if sort_by == "due_at":
            sort_column = Task.due_at
        elif sort_by == "priority":
            sort_column = Task.priority
        elif sort_by == "last_activity_at":
            sort_column = Task.last_activity_at

        if sort_dir.lower() == "asc":
            stmt = stmt.order_by(sort_column.asc())
        else:
            stmt = stmt.order_by(sort_column.desc())

        # 6. Pagination
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)

        result = await self.db.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def update(self, task: Task) -> Task:
        self.db.add(task)
        await self.db.flush()
        return task

    async def soft_delete(self, ctx: RequestContext, task_id: uuid.UUID) -> bool:
        """Performs tenant-safe soft deletion."""
        task = await self.get_by_id(ctx, task_id)
        if task is None:
            return False
        task.deleted_at = datetime.now(timezone.utc)
        self.db.add(task)
        await self.db.flush()
        return True

    async def soft_delete_for_lead(self, ctx: RequestContext, lead_id: uuid.UUID) -> int:
        """Soft delete all active tasks belonging to a lead inside the current organization."""
        stmt = (
            update(Task)
            .where(
                Task.lead_id == lead_id,
                Task.organization_id == ctx.tenant_id,
                Task.deleted_at.is_(None),
            )
            .values(deleted_at=datetime.now(timezone.utc))
        )
        res = await self.db.execute(stmt)
        await self.db.flush()
        return res.rowcount or 0
