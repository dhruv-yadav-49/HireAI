import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_request_context
from app.core.context import RequestContext
from app.core.exceptions import (
    ValidationException,
    WorkflowExecutionNotFoundException,
    WorkflowNotFoundException,
)
from app.db.session import get_db
from app.models.enums import WorkflowExecutionStatus, WorkflowTriggerType
from app.schemas.workflow import (
    WorkflowCreateRequest,
    WorkflowExecutionListResponse,
    WorkflowExecutionResponse,
    WorkflowListResponse,
    WorkflowResponse,
    WorkflowUpdateRequest,
)
from app.services.workflow_service import WorkflowService

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post(
    "",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a workflow",
    description="Creates a new workflow configuration with conditions and actions scoped to the organization.",
)
async def create_workflow(
    data: WorkflowCreateRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> WorkflowResponse:
    service = WorkflowService(db)
    workflow = await service.create_workflow(ctx, data)
    return WorkflowResponse.model_validate(workflow)


@router.get(
    "",
    response_model=WorkflowListResponse,
    summary="List workflows",
    description="Lists all workflows defined inside the active organization with filters, search and paging.",
)
async def list_workflows(
    trigger_type: Optional[WorkflowTriggerType] = None,
    enabled: Optional[bool] = None,
    search: Optional[str] = Query(None, description="Search by workflow name or description"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> WorkflowListResponse:
    service = WorkflowService(db)
    items, total = await service.repo.list_workflows(
        ctx=ctx,
        trigger_type=trigger_type,
        enabled=enabled,
        search=search,
        page=page,
        page_size=page_size,
    )
    return WorkflowListResponse(
        items=[WorkflowResponse.model_validate(w) for w in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/executions",
    response_model=WorkflowExecutionListResponse,
    summary="List workflow executions",
    description="Lists past workflow executions and step histories inside the organization.",
)
async def list_executions(
    workflow_id: Optional[uuid.UUID] = None,
    status: Optional[WorkflowExecutionStatus] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> WorkflowExecutionListResponse:
    service = WorkflowService(db)
    items, total = await service.execution_repo.list_executions(
        ctx=ctx,
        workflow_id=workflow_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return WorkflowExecutionListResponse(
        items=[WorkflowExecutionResponse.model_validate(e) for e in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/executions/{id}",
    response_model=WorkflowExecutionResponse,
    summary="Get execution details",
    description="Fetches full details and steps executed for a workflow execution log.",
)
async def get_execution(
    id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> WorkflowExecutionResponse:
    service = WorkflowService(db)
    execution = await service.execution_repo.get_execution_by_id(ctx, id)
    if execution is None:
        raise WorkflowExecutionNotFoundException()
    return WorkflowExecutionResponse.model_validate(execution)


@router.get(
    "/{id}",
    response_model=WorkflowResponse,
    summary="Get workflow details",
    description="Fetches full configuration details of a workflow rule.",
)
async def get_workflow(
    id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> WorkflowResponse:
    service = WorkflowService(db)
    workflow = await service.repo.get_by_id(ctx, id)
    if workflow is None:
        raise WorkflowNotFoundException()
    return WorkflowResponse.model_validate(workflow)


@router.patch(
    "/{id}",
    response_model=WorkflowResponse,
    summary="Update a workflow",
    description="Updates a workflow definition, enforcing optimistic locking version checks.",
)
async def update_workflow(
    id: uuid.UUID,
    data: WorkflowUpdateRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> WorkflowResponse:
    service = WorkflowService(db)
    workflow = await service.update_workflow(ctx, id, data)
    return WorkflowResponse.model_validate(workflow)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete workflow",
    description="Soft deletes the workflow configuration. Executions remain intact.",
)
async def delete_workflow(
    id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = WorkflowService(db)
    await service.repo.soft_delete(ctx, id)


@router.post(
    "/{id}/enable",
    response_model=WorkflowResponse,
    summary="Enable workflow",
    description="Enables a workflow for execution runs. Enforces version checks.",
)
async def enable_workflow(
    id: uuid.UUID,
    data: WorkflowUpdateRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> WorkflowResponse:
    service = WorkflowService(db)
    workflow = await service.enable_workflow(ctx, id, data.version)
    return WorkflowResponse.model_validate(workflow)


@router.post(
    "/{id}/disable",
    response_model=WorkflowResponse,
    summary="Disable workflow",
    description="Disables a workflow, preventing automatic triggers. Enforces version checks.",
)
async def disable_workflow(
    id: uuid.UUID,
    data: WorkflowUpdateRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> WorkflowResponse:
    service = WorkflowService(db)
    workflow = await service.disable_workflow(ctx, id, data.version)
    return WorkflowResponse.model_validate(workflow)


class ManualExecuteRequest(BaseModel):
    entity_type: str = Query(..., description="LEAD or TASK")
    entity_id: uuid.UUID = Query(..., description="Target object identifier")


@router.post(
    "/{id}/execute",
    response_model=WorkflowExecutionResponse,
    summary="Manually execute workflow",
    description="Forces execution of a workflow ruleset on a specific entity, ignoring condition triggers.",
)
async def execute_manual(
    id: uuid.UUID,
    req: ManualExecuteRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> WorkflowExecutionResponse:
    service = WorkflowService(db)
    execution = await service.execute_manually(
        ctx=ctx,
        workflow_id=id,
        entity_type=req.entity_type,
        entity_id=req.entity_id,
    )
    return WorkflowExecutionResponse.model_validate(execution)
