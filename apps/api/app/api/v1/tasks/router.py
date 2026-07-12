"""
app/api/v1/tasks/router.py

Protected Tasks API Endpoints:
  POST   /tasks             — Create a task
  GET    /tasks             — List tasks (filters, pagination, sort)
  GET    /tasks/{id}        — Get detailed task (with computed is_overdue)
  PATCH  /tasks/{id}        — Update task details (version check)
  DELETE /tasks/{id}        — Soft delete task
  POST   /tasks/{id}/complete — Mark task COMPLETED (requires version)
  POST   /tasks/{id}/reopen   — Reopen completed/cancelled task (requires version)
  POST   /tasks/{id}/cancel   — Cancel task (requires version)
  GET    /tasks/{id}/activities — Get activity timeline
"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_request_context
from app.core.context import RequestContext
from app.db.session import get_db
from app.models.enums import TaskPriority, TaskStatus, TaskType
from app.schemas.task import (
    TaskActivityResponse,
    TaskCreateRequest,
    TaskListResponse,
    TaskResponse,
    TaskUpdateRequest,
)
from app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskActionRequest(BaseModel):
    version: int = Field(..., description="Current version of the task for optimistic locking")


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a task",
    description="Creates a new task/follow-up scoped to a specific Lead and the caller's tenant.",
)
async def create_task(
    data: TaskCreateRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    service = TaskService(db)
    task = await service.create_task(ctx, data)
    return TaskResponse.model_validate(task)


@router.get(
    "",
    response_model=TaskListResponse,
    summary="List tasks",
    description="Lists active tasks in the current tenant with sorting, filters, search, and pagination.",
)
async def list_tasks(
    status: Optional[TaskStatus] = None,
    priority: Optional[TaskPriority] = None,
    type: Optional[TaskType] = None,
    lead_id: Optional[uuid.UUID] = None,
    assigned_to: Optional[uuid.UUID] = None,
    due_before: Optional[datetime] = None,
    due_after: Optional[datetime] = None,
    search: Optional[str] = Query(None, description="Search by task title or description"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at", description="Sort by created_at, due_at, priority, or last_activity_at"),
    sort_dir: str = Query("desc", description="asc or desc"),
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> TaskListResponse:
    service = TaskService(db)
    items, total = await service.task_repo.list(
        ctx=ctx,
        status=status.value if status else None,
        priority=priority.value if priority else None,
        type_=type.value if type else None,
        lead_id=lead_id,
        assigned_to=assigned_to,
        due_before=due_before,
        due_after=due_after,
        search=search,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return TaskListResponse(
        items=[TaskResponse.model_validate(t) for t in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{id}",
    response_model=TaskResponse,
    summary="Get task details",
    description="Fetches a task's details. Returns 404 if not found or belongs to another tenant.",
)
async def get_task(
    id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    service = TaskService(db)
    task = await service.task_repo.get_by_id(ctx, id)
    if task is None:
        from app.core.exceptions import TaskNotFoundException
        raise TaskNotFoundException()
    return TaskResponse.model_validate(task)


@router.patch(
    "/{id}",
    response_model=TaskResponse,
    summary="Update a task",
    description="Updates a task's details, enforcing optimistic locking version checks.",
)
async def update_task(
    id: uuid.UUID,
    data: TaskUpdateRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    service = TaskService(db)
    task = await service.update_task(ctx, id, data)
    return TaskResponse.model_validate(task)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete a task",
    description="Soft deletes the task.",
)
async def delete_task(
    id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = TaskService(db)
    await service.soft_delete_task(ctx, id)


@router.post(
    "/{id}/complete",
    response_model=TaskResponse,
    summary="Mark task completed",
    description="Marks the task status as COMPLETED and sets completed_at to now. Enforces optimistic lock version.",
)
async def complete_task(
    id: uuid.UUID,
    data: TaskActionRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    service = TaskService(db)
    task = await service.complete_task(ctx, id, data.version)
    return TaskResponse.model_validate(task)


@router.post(
    "/{id}/reopen",
    response_model=TaskResponse,
    summary="Reopen task",
    description="Reopens a completed or cancelled task back to OPEN status. Clears completed_at.",
)
async def reopen_task(
    id: uuid.UUID,
    data: TaskActionRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    service = TaskService(db)
    task = await service.reopen_task(ctx, id, data.version)
    return TaskResponse.model_validate(task)


@router.post(
    "/{id}/cancel",
    response_model=TaskResponse,
    summary="Cancel task",
    description="Cancels an open or in-progress task. Rejects if already COMPLETED.",
)
async def cancel_task(
    id: uuid.UUID,
    data: TaskActionRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    service = TaskService(db)
    task = await service.cancel_task(ctx, id, data.version)
    return TaskResponse.model_validate(task)


@router.get(
    "/{id}/activities",
    response_model=list[TaskActivityResponse],
    summary="Get activities timeline",
    description="Fetches timeline activity logs for the task, ordered newest first.",
)
async def list_activities(
    id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> list[TaskActivityResponse]:
    service = TaskService(db)
    activities = await service.list_activities(ctx, id)
    return [TaskActivityResponse.model_validate(a) for a in activities]
