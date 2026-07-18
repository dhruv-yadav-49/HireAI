from __future__ import annotations
import uuid
import hashlib
from typing import Optional, Any
from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.enums import AIJobStatus, QueueType, JobFailureCategory
from app.models.ai_job import AIJob
from app.models.ai_job_result import AIJobResult
from app.models.ai_worker import AIWorker
from app.repositories.job_repository import QueueRepository
from app.queue.queue_manager import QueueManager
from app.queue.dead_letter_queue import DeadLetterQueue
from app.jobs.job_state_machine import JobStateMachine

class DistributedExecutionService:
    """Gateway service coordinating job submissions, cancellations, retries, and worker tracking.

    ADR-019: Idempotency keys, Backpressure limits.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def submit_job(
        self,
        ctx: RequestContext,
        job_type: str,
        priority: int = 10,
        queue_name: QueueType = QueueType.DEFAULT,
        idempotency_key: Optional[str] = None
    ) -> AIJob:
        """Enforces backpressure throttling, checks idempotency keys, and schedules work."""
        repo = QueueRepository(self.db)

        # Check backpressure limits before accepting
        await QueueManager.check_backpressure(queue_name.value)

        # If idempotency key provided, check if already exists
        request_hash = None
        if idempotency_key:
            existing = await repo.get_job_by_idempotency_key(idempotency_key)
            if existing:
                return existing
            # Compute hash for request payload context verification
            request_hash = hashlib.md5(f"{job_type}:{priority}:{queue_name.value}".encode()).hexdigest()

        # Create and enqueue job record
        job = await repo.create_job(
            org_id=ctx.tenant_id,
            job_type=job_type,
            priority=priority,
            queue_name=queue_name,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            requested_by=ctx.user.id,
            created_by=ctx.user.id,
            source="API"
        )
        return job

    async def get_job_status(self, ctx: RequestContext, job_id: uuid.UUID) -> dict[str, Any]:
        """Fetches current execution state, progress updates, and checkpoints."""
        repo = QueueRepository(self.db)
        job = await repo.get_job(job_id)
        if not job or job.organization_id != ctx.tenant_id:
            raise ValueError("Job not found or access denied.")

        return {
            "job_id": str(job.id),
            "status": job.status.value,
            "priority": job.priority,
            "queue_name": job.queue_name.value,
            "progress_percent": job.progress_percent,
            "current_step": job.current_step,
            "total_steps": job.total_steps,
            "retry_count": job.retry_count,
            "max_retries": job.max_retries,
            "lease_owner": job.lease_owner,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "created_at": job.created_at.isoformat()
        }

    async def get_job_result(self, ctx: RequestContext, job_id: uuid.UUID) -> dict[str, Any]:
        """Loads finalized results details."""
        repo = QueueRepository(self.db)
        job = await repo.get_job(job_id)
        if not job or job.organization_id != ctx.tenant_id:
            raise ValueError("Job not found or access denied.")

        stmt = select(AIJobResult).where(AIJobResult.job_id == job_id)
        res = await self.db.execute(stmt)
        result = res.scalar_one_or_none()
        if not result:
            return {"status": job.status.value, "output": None}

        return {
            "job_id": str(job_id),
            "status": result.status.value,
            "output_json": result.output_json,
            "error_message": result.error_message,
            "failure_reason": result.failure_reason,
            "failure_category": result.failure_category.value if result.failure_category else None,
            "execution_time_ms": result.execution_time_ms,
            "token_usage": result.token_usage,
            "cost": result.cost,
            "created_at": result.created_at.isoformat()
        }

    async def cancel_job(self, ctx: RequestContext, job_id: uuid.UUID) -> dict[str, Any]:
        """Requests cancellation by updating status to CANCELLED."""
        repo = QueueRepository(self.db)
        job = await repo.get_job(job_id)
        if not job or job.organization_id != ctx.tenant_id:
            raise ValueError("Job not found or access denied.")

        if not JobStateMachine.validate_transition(job.status, AIJobStatus.CANCELLED):
            raise ValueError(f"Cannot cancel job in {job.status.value} state.")

        # Update to CANCELLED in DB. Running workers will pick this up cooperatively.
        stmt = update(AIJob).where(AIJob.id == job_id).values(
            status=AIJobStatus.CANCELLED,
            cancelled_at=datetime.now(timezone.utc)
        )
        await self.db.execute(stmt)
        await self.db.flush()

        await repo.add_job_event(job_id, "job.cancelled", {})
        return {"job_id": str(job_id), "status": "CANCELLED"}

    async def retry_job(self, ctx: RequestContext, job_id: uuid.UUID) -> bool:
        """Manually replays/retries an exhausted job from DLQ back to active queue."""
        repo = QueueRepository(self.db)
        job = await repo.get_job(job_id)
        if not job or job.organization_id != ctx.tenant_id:
            raise ValueError("Job not found or access denied.")

        return await DeadLetterQueue.replay_job(self.db, job_id)

    async def list_workers(self, ctx: RequestContext) -> list[dict[str, Any]]:
        """Lists registered execution worker nodes."""
        stmt = select(AIWorker)
        res = await self.db.execute(stmt)
        workers = res.scalars().all()
        return [
            {
                "id": str(w.id),
                "hostname": w.hostname,
                "worker_name": w.worker_name,
                "status": w.status.value,
                "cpu_usage": w.cpu_usage,
                "memory_usage": w.memory_usage,
                "running_jobs": w.running_jobs,
                "heartbeat_at": w.heartbeat_at.isoformat(),
                "started_at": w.started_at.isoformat()
            }
            for w in workers
        ]

    async def get_queue_stats(self, ctx: RequestContext) -> dict[str, Any]:
        """Compiles stats of active queues."""
        return QueueManager.get_statistics()
