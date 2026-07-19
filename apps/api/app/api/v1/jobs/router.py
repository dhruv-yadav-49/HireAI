import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.api.dependencies import get_current_context
from app.core.context import RequestContext
from app.db.session import get_db
from app.models.enums import QueueType
from app.services.distributed_execution_service import DistributedExecutionService
from app.governance.action_interceptor import ActionInterceptor
from app.security.security_service_helper import build_security_ctx_from_request_ctx

router = APIRouter(prefix="/jobs", tags=["Distributed Jobs"])


# ── Pydantic Request Schemas ──────────────────────────────────────────────────

class SubmitJobRequest(BaseModel):
    job_type: str = Field(..., description="The type of AI workflow run (e.g. Sales, Marketing)")
    priority: int = Field(default=10, ge=0, le=100)
    queue_name: QueueType = Field(default=QueueType.DEFAULT)
    idempotency_key: Optional[str] = Field(default=None)


# ── Route Handlers ────────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def submit_job(
    body: SubmitJobRequest,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    svc = DistributedExecutionService(db)
    # ActionInterceptor pre-check (Sprint 7D Governance)
    sec_ctx = build_security_ctx_from_request_ctx(ctx)
    await ActionInterceptor.check_action(
        db=db,
        sec_ctx=sec_ctx,
        action_type=body.job_type,
        job_type=body.job_type,
    )
    try:
        job = await svc.submit_job(
            ctx=ctx,
            job_type=body.job_type,
            priority=body.priority,
            queue_name=body.queue_name,
            idempotency_key=body.idempotency_key
        )
        return {
            "job_id": str(job.id),
            "status": job.status.value,
            "idempotency_key": job.idempotency_key
        }
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))


@router.get("/{id}")
async def get_job(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    svc = DistributedExecutionService(db)
    try:
        return await svc.get_job_status(ctx, id)
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(val_err))


@router.get("/{id}/result")
async def get_job_result(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    svc = DistributedExecutionService(db)
    try:
        return await svc.get_job_result(ctx, id)
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(val_err))


@router.post("/{id}/cancel")
async def cancel_job(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    svc = DistributedExecutionService(db)
    try:
        return await svc.cancel_job(ctx, id)
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))


@router.post("/{id}/retry")
async def retry_job(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    svc = DistributedExecutionService(db)
    try:
        success = await svc.retry_job(ctx, id)
        return {"success": success}
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))


@router.get("/system/workers")
async def list_workers(
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    svc = DistributedExecutionService(db)
    return await svc.list_workers(ctx)


@router.get("/system/queues")
async def get_queues(
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    svc = DistributedExecutionService(db)
    return await svc.get_queue_stats(ctx)
