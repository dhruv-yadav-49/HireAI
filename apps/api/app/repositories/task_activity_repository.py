import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.task import Task
from app.models.task_activity import TaskActivity


class TaskActivityRepository:
    """Timeline activities repository for Tasks. Immutable (append-only timeline rule).
    No update or delete operations are exposed.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_activity(self, activity: TaskActivity) -> TaskActivity:
        self.db.add(activity)
        await self.db.flush()
        return activity

    async def list_for_task(self, ctx: RequestContext, task_id: uuid.UUID) -> list[TaskActivity]:
        """Fetch all activities for a task within the tenant, ordered newest-first."""
        stmt = (
            select(TaskActivity)
            .join(Task, TaskActivity.task_id == Task.id)
            .where(
                TaskActivity.task_id == task_id,
                Task.organization_id == ctx.tenant_id,
            )
            .order_by(TaskActivity.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
