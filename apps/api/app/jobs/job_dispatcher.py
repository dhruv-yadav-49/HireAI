from __future__ import annotations
import uuid
import logging
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AIJobStatus, WorkerStatus
from app.models.ai_worker import AIWorker
from app.models.ai_job import AIJob
from app.repositories.job_repository import QueueRepository
from app.jobs.job_executor import JobExecutor

logger = logging.getLogger(__name__)


class JobDispatcher:
    """Dispatches queued execution jobs to active idle worker processes.

    ADR-019: Worker Independence, Lease-Based Ownership.
    """

    @classmethod
    async def dispatch_next(cls, db: AsyncSession, queue_name: str = "DEFAULT") -> Optional[uuid.UUID]:
        """Polls queue, selects idle worker, updates lease ownership, and dispatches."""
        repo = QueueRepository(db)

        # 1. Search for an available idle worker
        worker_stmt = select(AIWorker).where(AIWorker.status == WorkerStatus.IDLE).limit(1)
        res_worker = await db.execute(worker_stmt)
        worker = res_worker.scalar_one_or_none()
        if not worker:
            logger.debug("No IDLE worker process available for dispatching.")
            return None

        # 2. Dequeue item
        queued_item = await repo.dequeue_job(queue_name)
        if not queued_item:
            return None

        job_id = queued_item["job_id"]
        job = await repo.get_job(job_id)
        if not job or job.status != AIJobStatus.QUEUED:
            # Job was cancelled or already processed, acknowledge and exit
            await repo.ack_job(queue_name, job_id)
            return None

        # 3. Claim job with worker lease and update state to DISPATCHED (CTO refinement #1)
        from datetime import datetime, timezone, timedelta
        lease_duration = 300  # 5 minutes
        stmt_job = update(AIJob).where(AIJob.id == job_id).values(
            status=AIJobStatus.DISPATCHED,
            worker_id=worker.id,
            lease_owner=worker.worker_name,
            lease_expires_at=datetime.now(timezone.utc) + timedelta(seconds=lease_duration)
        )
        await db.execute(stmt_job)

        # 4. Map worker to busy status
        stmt_worker = update(AIWorker).where(AIWorker.id == worker.id).values(
            status=WorkerStatus.BUSY,
            current_job_id=job_id,
            running_jobs=1
        )
        await db.execute(stmt_worker)
        await db.flush()

        await repo.add_job_event(job_id, "job.dispatched", {"worker_id": str(worker.id)})
        logger.info(f"Dispatched job {job_id} to worker {worker.worker_name} (ID: {worker.id})")

        # 5. Execute job asynchronously in worker context (in-process for verification tests)
        try:
            await JobExecutor.execute_job(db, job_id)
        finally:
            # Revert worker back to IDLE
            stmt_idle = update(AIWorker).where(AIWorker.id == worker.id).values(
                status=WorkerStatus.IDLE,
                current_job_id=None,
                running_jobs=0
            )
            await db.execute(stmt_idle)
            await db.flush()

            # Acknowledge completion and release visibility timeout tracker
            await repo.ack_job(queue_name, job_id)

        return job_id
