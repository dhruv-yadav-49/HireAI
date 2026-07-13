import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_request_context
from app.core.context import RequestContext
from app.db.session import get_db
from app.models.enums import JobStatus
from app.models.organization import Organization
from app.models.scheduled_job import JobExecution, ScheduledJob
from app.schemas.scheduler import (
    JobExecutionListResponse,
    JobExecutionResponse,
    ScheduledJobListResponse,
    ScheduledJobResponse,
    ScheduledJobCreateRequest,
    ScheduledJobUpdateRequest,
)
from app.services.cron_service import CronService
from app.services.scheduler_service import SchedulerService

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])


@router.post("/jobs", response_model=ScheduledJobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    req: ScheduledJobCreateRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """Creates a scheduled recurring job for the organization."""
    # Resolve org timezone
    org_tz = "UTC"
    org_stmt = select(Organization).where(Organization.id == ctx.tenant_id)
    org_res = await db.execute(org_stmt)
    org = org_res.scalar()
    if org and org.timezone:
        org_tz = org.timezone

    job_tz = req.timezone or org_tz

    now = datetime.now(timezone.utc)
    # Calculate next execution run
    try:
        next_run = CronService.get_next_run(req.cron_expression, now, job_tz)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to calculate initial next run schedule: {str(e)}",
        )

    job = ScheduledJob(
        organization_id=ctx.tenant_id,
        name=req.name,
        description=req.description,
        cron_expression=req.cron_expression,
        job_type=req.job_type,
        payload=req.payload or {},
        payload_version=req.payload_version or 1,
        status=req.status or JobStatus.ACTIVE,
        max_retries=req.max_retries or 3,
        retry_count=0,
        timezone=req.timezone,
        version=1,
        created_by=ctx.user.id,
        updated_by=ctx.user.id,
        next_run_at=next_run,
    )

    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


@router.get("/jobs", response_model=ScheduledJobListResponse)
async def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """Lists scheduled jobs for the organization."""
    offset = (page - 1) * page_size

    total = await db.scalar(
        select(func.count(ScheduledJob.id)).where(
            ScheduledJob.organization_id == ctx.tenant_id,
            ScheduledJob.deleted_at.is_(None),
        )
    )

    # Query paginated list
    stmt = (
        select(ScheduledJob)
        .where(
            ScheduledJob.organization_id == ctx.tenant_id,
            ScheduledJob.deleted_at.is_(None),
        )
        .order_by(ScheduledJob.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    res = await db.execute(stmt)
    items = res.scalars().all()

    return ScheduledJobListResponse(
        items=items,
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.patch("/jobs/{job_id}", response_model=ScheduledJobResponse)
async def update_job(
    job_id: uuid.UUID,
    req: ScheduledJobUpdateRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """Updates scheduled job configuration with optimistic locking version check."""
    # Find job
    stmt = select(ScheduledJob).where(
        ScheduledJob.id == job_id,
        ScheduledJob.organization_id == ctx.tenant_id,
        ScheduledJob.deleted_at.is_(None),
    )
    res = await db.execute(stmt)
    job = res.scalar()

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheduled job not found.",
        )

    # Check optimistic locking version
    if job.version != req.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Optimistic locking conflict. Configuration has been modified by another process.",
        )

    # Apply edits
    if req.name is not None:
        job.name = req.name
    if req.description is not None:
        job.description = req.description
    if req.payload is not None:
        job.payload = req.payload
    if req.payload_version is not None:
        job.payload_version = req.payload_version
    if req.max_retries is not None:
        job.max_retries = req.max_retries

    # Check timezone or cron expression update to recalculate next run
    recalc_run = False
    if req.cron_expression is not None and req.cron_expression != job.cron_expression:
        job.cron_expression = req.cron_expression
        recalc_run = True
    if req.timezone is not None and req.timezone != job.timezone:
        job.timezone = req.timezone
        recalc_run = True
    if req.status is not None and req.status != job.status:
        job.status = req.status
        recalc_run = True

    if recalc_run and job.status == JobStatus.ACTIVE:
        org_tz = "UTC"
        org_stmt = select(Organization).where(Organization.id == ctx.tenant_id)
        org_res = await db.execute(org_stmt)
        org = org_res.scalar()
        if org and org.timezone:
            org_tz = org.timezone

        job_tz = job.timezone or org_tz
        now = datetime.now(timezone.utc)
        try:
            job.next_run_at = CronService.get_next_run(job.cron_expression, now, job_tz)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to recalculate next run schedule: {str(e)}",
            )

    # Bump version and set editor metadata
    job.version += 1
    job.updated_by = ctx.user.id
    job.updated_at = datetime.now(timezone.utc)

    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """Soft deletes scheduled job configuration."""
    stmt = select(ScheduledJob).where(
        ScheduledJob.id == job_id,
        ScheduledJob.organization_id == ctx.tenant_id,
        ScheduledJob.deleted_at.is_(None),
    )
    res = await db.execute(stmt)
    job = res.scalar()

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheduled job not found.",
        )

    job.deleted_at = datetime.now(timezone.utc)
    job.updated_at = datetime.now(timezone.utc)
    job.updated_by = ctx.user.id
    db.add(job)
    await db.commit()


@router.post("/jobs/{job_id}/run", response_model=JobExecutionResponse)
async def force_run_job(
    job_id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """Forcibly triggers execution of a scheduled job immediately (synchronously inside request for S4B testing)."""
    # Fetch job
    stmt = select(ScheduledJob).where(
        ScheduledJob.id == job_id,
        ScheduledJob.organization_id == ctx.tenant_id,
        ScheduledJob.deleted_at.is_(None),
    )
    res = await db.execute(stmt)
    job = res.scalar()

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheduled job not found.",
        )

    # Force tick execution by setting next_run_at to past, and triggering tick!
    job.next_run_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.add(job)
    await db.commit()

    # Trigger scheduler tick
    await SchedulerService.tick(db)

    # Retrieve the execution log run details
    exec_stmt = (
        select(JobExecution)
        .where(
            JobExecution.job_id == job.id,
            JobExecution.organization_id == ctx.tenant_id,
        )
        .order_by(JobExecution.started_at.desc())
        .limit(1)
    )
    exec_res = await db.execute(exec_stmt)
    execution = exec_res.scalar()

    if execution is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Job was forced to run but execution logs failed to create.",
        )

    return execution


@router.get("/executions", response_model=JobExecutionListResponse)
async def list_executions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """Lists scheduled job execution logs for the organization."""
    offset = (page - 1) * page_size

    total = await db.scalar(
        select(func.count(JobExecution.id)).where(
            JobExecution.organization_id == ctx.tenant_id,
        )
    )

    stmt = (
        select(JobExecution)
        .where(
            JobExecution.organization_id == ctx.tenant_id,
        )
        .order_by(JobExecution.started_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    res = await db.execute(stmt)
    items = res.scalars().all()

    return JobExecutionListResponse(
        items=items,
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.get("/executions/{execution_id}", response_model=JobExecutionResponse)
async def get_execution(
    execution_id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves details of a single scheduled job execution log."""
    stmt = select(JobExecution).where(
        JobExecution.id == execution_id,
        JobExecution.organization_id == ctx.tenant_id,
    )
    res = await db.execute(stmt)
    execution = res.scalar()

    if execution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job execution log not found.",
        )

    return execution
