import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.events import DomainEvent, get_event_publisher
from app.core.exceptions import (
    ConcurrentUpdateException,
    LeadNotFoundException,
    TaskNotFoundException,
    ValidationException,
)
from app.models.enums import ActorType, TaskActivityType, TaskStatus
from app.models.task import Task
from app.models.task_activity import TaskActivity
from app.repositories.lead_repository import LeadRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.task_activity_repository import TaskActivityRepository
from app.schemas.task import TaskCreateRequest, TaskUpdateRequest

_VALID_TRANSITIONS = {
    TaskStatus.OPEN: {TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED, TaskStatus.CANCELLED},
    TaskStatus.IN_PROGRESS: {TaskStatus.COMPLETED, TaskStatus.CANCELLED},
    TaskStatus.COMPLETED: {TaskStatus.OPEN},
    TaskStatus.CANCELLED: {TaskStatus.OPEN},
}


class TaskService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.task_repo = TaskRepository(db)
        self.lead_repo = LeadRepository(db)
        self.activity_repo = TaskActivityRepository(db)

    async def create_task(self, ctx: RequestContext, data: TaskCreateRequest) -> Task:
        """Create a task for a lead, checking tenant boundaries, due dates, and reminders."""
        # 1. Check if lead exists in the same tenant
        lead = await self.lead_repo.get_by_id(ctx, data.lead_id)
        if lead is None:
            raise LeadNotFoundException()

        # 2. Instantiate and create task
        task = Task(
            organization_id=ctx.tenant_id,
            lead_id=data.lead_id,
            created_by=ctx.user.id,
            updated_by=ctx.user.id,
            assigned_to=data.assigned_to,
            title=data.title,
            description=data.description,
            status=TaskStatus.OPEN,
            priority=data.priority,
            type=data.type,
            due_at=data.due_at,
            reminder_at=data.reminder_at,
            last_activity_at=datetime.now(timezone.utc),
        )
        await self.task_repo.create(task)

        # 3. Log timeline activity with request tracing ID correlation
        activity_meta = {
            "assigned_to": str(task.assigned_to) if task.assigned_to else None,
            "request_id": str(ctx.request_id),
        }
        await self._log_activity(
            task_id=task.id,
            actor_id=ctx.user.id,
            actor_type=ActorType.USER,
            activity_type=TaskActivityType.CREATED,
            metadata=activity_meta,
        )

        # Publish task.created domain event
        event = DomainEvent(
            event_name="task.created",
            tenant_id=ctx.tenant_id,
            request_id=ctx.request_id,
            actor_id=ctx.user.id,
            payload={
                "task_id": str(task.id),
                "lead_id": str(task.lead_id),
                "assigned_to": str(task.assigned_to) if task.assigned_to else None,
            },
        )
        await self.db.commit()
        await get_event_publisher().publish(event)
        return task

    async def update_task(
        self, ctx: RequestContext, task_id: uuid.UUID, data: TaskUpdateRequest
    ) -> Task:
        """Update a task's details, verifying transition rules, date logic, and optimistic locks."""
        task = await self.task_repo.get_by_id(ctx, task_id)
        if task is None:
            raise TaskNotFoundException()

        # Optimistic locking check
        if task.version != data.version:
            raise ConcurrentUpdateException()

        updates: dict[str, Any] = {}
        activities_to_log: list[tuple[TaskActivityType, dict[str, Any]]] = []

        # Validate date modifications if updated
        due_at = data.due_at if data.due_at is not None else task.due_at
        reminder_at = data.reminder_at if data.reminder_at is not None else task.reminder_at
        if reminder_at and due_at and reminder_at >= due_at:
            raise ValidationException("reminder_at must be before due_at.")

        # Validate status change and transitions
        if data.status is not None and data.status != task.status:
            allowed = _VALID_TRANSITIONS.get(task.status, set())
            if data.status not in allowed:
                raise ValidationException(
                    f"Invalid task status transition from '{task.status.value}' to '{data.status.value}'."
                )
            
            updates["status"] = data.status
            activities_to_log.append(
                (
                    TaskActivityType.STATUS_CHANGED,
                    {
                        "old_status": task.status.value,
                        "new_status": data.status.value,
                        "request_id": str(ctx.request_id),
                    },
                )
            )

            # Automatically manage completed_at date
            if data.status == TaskStatus.COMPLETED:
                updates["completed_at"] = datetime.now(timezone.utc)
            elif task.status == TaskStatus.COMPLETED:
                # Transitioning back to open/cancelled clears completed_at
                updates["completed_at"] = None

        # Validate assignee change
        if data.assigned_to is not None and data.assigned_to != task.assigned_to:
            activities_to_log.append(
                (
                    TaskActivityType.ASSIGNED,
                    {
                        "old_assignee_id": str(task.assigned_to) if task.assigned_to else None,
                        "new_assignee_id": str(data.assigned_to) if data.assigned_to else None,
                        "request_id": str(ctx.request_id),
                    },
                )
            )
            updates["assigned_to"] = data.assigned_to

        # Simple updates
        for field in ("title", "description", "priority", "type", "due_at", "reminder_at"):
            val = getattr(data, field)
            if val is not None:
                updates[field] = val

        if updates:
            # Automate last_activity_at bump and update fields
            updates["last_activity_at"] = datetime.now(timezone.utc)
            updates["updated_by"] = ctx.user.id

            # Atomic update using optimistic locking
            stmt = (
                update(Task)
                .where(
                    Task.id == task_id,
                    Task.organization_id == ctx.tenant_id,
                    Task.version == task.version,
                )
                .values(**updates, version=task.version + 1)
            )
            result = await self.db.execute(stmt)
            if result.rowcount == 0:
                raise ConcurrentUpdateException()

            # Record generic update activity
            activities_to_log.append(
                (
                    TaskActivityType.UPDATED,
                    {"updated_fields": list(updates.keys()), "request_id": str(ctx.request_id)},
                )
            )

            # Log all activities gathered
            for act_type, meta in activities_to_log:
                await self._log_activity(
                    task_id=task_id,
                    actor_id=ctx.user.id,
                    actor_type=ActorType.USER,
                    activity_type=act_type,
                    metadata=meta,
                )

            # Publish domain events
            events_to_publish = []
            if "status" in updates:
                event = DomainEvent(
                    event_name="task.status_changed",
                    tenant_id=ctx.tenant_id,
                    request_id=ctx.request_id,
                    actor_id=ctx.user.id,
                    payload={
                        "task_id": str(task_id),
                        "old_status": task.status.value,
                        "new_status": updates["status"].value,
                    }
                )
                events_to_publish.append(event)
            
            if "assigned_to" in updates:
                event = DomainEvent(
                    event_name="task.assigned",
                    tenant_id=ctx.tenant_id,
                    request_id=ctx.request_id,
                    actor_id=ctx.user.id,
                    payload={
                        "task_id": str(task_id),
                        "old_assignee_id": str(task.assigned_to) if task.assigned_to else None,
                        "new_assignee_id": str(updates["assigned_to"]) if updates["assigned_to"] else None,
                    }
                )
                events_to_publish.append(event)

            # Generic task update event
            event = DomainEvent(
                event_name="task.updated",
                tenant_id=ctx.tenant_id,
                request_id=ctx.request_id,
                actor_id=ctx.user.id,
                payload={
                    "task_id": str(task_id),
                    "updated_fields": list(updates.keys()),
                }
            )
            events_to_publish.append(event)

            await self.db.commit()
            await self.db.refresh(task)

            for ev in events_to_publish:
                await get_event_publisher().publish(ev)

        return task

    async def complete_task(self, ctx: RequestContext, task_id: uuid.UUID, version: int) -> Task:
        """Mark task completed (idempotent, sets completed_at = now)."""
        task = await self.task_repo.get_by_id(ctx, task_id)
        if task is None:
            raise TaskNotFoundException()

        if task.status == TaskStatus.COMPLETED:
            return task  # Idempotent return

        if task.version != version:
            raise ConcurrentUpdateException()

        now = datetime.now(timezone.utc)
        stmt = (
            update(Task)
            .where(
                Task.id == task_id,
                Task.organization_id == ctx.tenant_id,
                Task.version == task.version,
            )
            .values(
                status=TaskStatus.COMPLETED,
                completed_at=now,
                last_activity_at=now,
                updated_by=ctx.user.id,
                version=task.version + 1,
            )
        )
        result = await self.db.execute(stmt)
        if result.rowcount == 0:
            raise ConcurrentUpdateException()

        await self._log_activity(
            task_id=task_id,
            actor_id=ctx.user.id,
            actor_type=ActorType.USER,
            activity_type=TaskActivityType.COMPLETED,
            metadata={"completed_at": now.isoformat(), "request_id": str(ctx.request_id)},
        )

        # Publish task.status_changed event
        event = DomainEvent(
            event_name="task.status_changed",
            tenant_id=ctx.tenant_id,
            request_id=ctx.request_id,
            actor_id=ctx.user.id,
            payload={
                "task_id": str(task_id),
                "old_status": task.status.value,
                "new_status": TaskStatus.COMPLETED.value,
            }
        )
        await self.db.commit()
        await self.db.refresh(task)
        await get_event_publisher().publish(event)
        return task

    async def reopen_task(self, ctx: RequestContext, task_id: uuid.UUID, version: int) -> Task:
        """Reopen a completed or cancelled task back to OPEN status (clears completed_at)."""
        task = await self.task_repo.get_by_id(ctx, task_id)
        if task is None:
            raise TaskNotFoundException()

        if task.status == TaskStatus.OPEN:
            return task  # Idempotent

        if task.version != version:
            raise ConcurrentUpdateException()

        now = datetime.now(timezone.utc)
        stmt = (
            update(Task)
            .where(
                Task.id == task_id,
                Task.organization_id == ctx.tenant_id,
                Task.version == task.version,
            )
            .values(
                status=TaskStatus.OPEN,
                completed_at=None,
                last_activity_at=now,
                updated_by=ctx.user.id,
                version=task.version + 1,
            )
        )
        result = await self.db.execute(stmt)
        if result.rowcount == 0:
            raise ConcurrentUpdateException()

        await self._log_activity(
            task_id=task_id,
            actor_id=ctx.user.id,
            actor_type=ActorType.USER,
            activity_type=TaskActivityType.REOPENED,
            metadata={"request_id": str(ctx.request_id)},
        )

        # Publish task.status_changed event
        event = DomainEvent(
            event_name="task.status_changed",
            tenant_id=ctx.tenant_id,
            request_id=ctx.request_id,
            actor_id=ctx.user.id,
            payload={
                "task_id": str(task_id),
                "old_status": task.status.value,
                "new_status": TaskStatus.OPEN.value,
            }
        )
        await self.db.commit()
        await self.db.refresh(task)
        await get_event_publisher().publish(event)
        return task

    async def cancel_task(self, ctx: RequestContext, task_id: uuid.UUID, version: int) -> Task:
        """Cancel an OPEN or IN_PROGRESS task (cannot cancel COMPLETED)."""
        task = await self.task_repo.get_by_id(ctx, task_id)
        if task is None:
            raise TaskNotFoundException()

        if task.status == TaskStatus.CANCELLED:
            return task  # Idempotent

        if task.status == TaskStatus.COMPLETED:
            raise ValidationException("Cannot cancel a completed task.")

        if task.version != version:
            raise ConcurrentUpdateException()

        now = datetime.now(timezone.utc)
        stmt = (
            update(Task)
            .where(
                Task.id == task_id,
                Task.organization_id == ctx.tenant_id,
                Task.version == task.version,
            )
            .values(
                status=TaskStatus.CANCELLED,
                last_activity_at=now,
                updated_by=ctx.user.id,
                version=task.version + 1,
            )
        )
        result = await self.db.execute(stmt)
        if result.rowcount == 0:
            raise ConcurrentUpdateException()

        await self._log_activity(
            task_id=task_id,
            actor_id=ctx.user.id,
            actor_type=ActorType.USER,
            activity_type=TaskActivityType.CANCELLED,
            metadata={"request_id": str(ctx.request_id)},
        )

        # Publish task.status_changed event
        event = DomainEvent(
            event_name="task.status_changed",
            tenant_id=ctx.tenant_id,
            request_id=ctx.request_id,
            actor_id=ctx.user.id,
            payload={
                "task_id": str(task_id),
                "old_status": task.status.value,
                "new_status": TaskStatus.CANCELLED.value,
            }
        )
        await self.db.commit()
        await self.db.refresh(task)
        await get_event_publisher().publish(event)
        return task

    async def soft_delete_task(self, ctx: RequestContext, task_id: uuid.UUID) -> None:
        task = await self.task_repo.get_by_id(ctx, task_id)
        if task is None:
            raise TaskNotFoundException()

        await self.task_repo.soft_delete(ctx, task_id)

        # Publish task.deleted event
        event = DomainEvent(
            event_name="task.deleted",
            tenant_id=ctx.tenant_id,
            request_id=ctx.request_id,
            actor_id=ctx.user.id,
            payload={
                "task_id": str(task_id),
            }
        )
        await self.db.commit()
        await get_event_publisher().publish(event)

    async def list_activities(self, ctx: RequestContext, task_id: uuid.UUID) -> list[TaskActivity]:
        task = await self.task_repo.get_by_id(ctx, task_id)
        if task is None:
            raise TaskNotFoundException()

        return await self.activity_repo.list_for_task(ctx, task_id)

    # ── Helpers ────────────────────────────────────────────────────────────────

    async def _log_activity(
        self,
        task_id: uuid.UUID,
        actor_id: uuid.UUID | None,
        actor_type: ActorType,
        activity_type: TaskActivityType,
        metadata: dict[str, Any],
    ) -> None:
        # Enforce metadata structure validations
        if activity_type == TaskActivityType.STATUS_CHANGED:
            if "old_status" not in metadata or "new_status" not in metadata:
                raise ValueError("STATUS_CHANGED activity requires 'old_status' and 'new_status'")
        elif activity_type == TaskActivityType.ASSIGNED:
            if "old_assignee_id" not in metadata or "new_assignee_id" not in metadata:
                raise ValueError("ASSIGNED activity requires 'old_assignee_id' and 'new_assignee_id'")
        elif activity_type == TaskActivityType.COMPLETED:
            if "completed_at" not in metadata:
                raise ValueError("COMPLETED activity requires 'completed_at'")

        if "request_id" not in metadata:
            raise ValueError("All task activities must contain correlation 'request_id' metadata.")

        activity = TaskActivity(
            task_id=task_id,
            actor_id=actor_id,
            actor_type=actor_type,
            activity_type=activity_type,
            event_metadata=metadata,
            metadata_version=1,
        )
        await self.activity_repo.create_activity(activity)
