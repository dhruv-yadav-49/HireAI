from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AIJobStatus, WorkerStatus, QueueType
from app.models.ai_worker import AIWorker
from app.models.ai_job import AIJob
from app.repositories.job_repository import QueueRepository

logger = logging.getLogger(__name__)


class WorkerHealth:
    """Detects failed worker instances, offlines them, and recovers stuck execution leases.

    CTO refinement #1: Lease expiration recovery.
    """

    @classmethod
    async def monitor_heartbeats_and_recover(cls, db: AsyncSession, threshold_sec: int = 90) -> dict:
        """Finds workers without heartbeats, marks them OFFLINE, and requeues active leases."""
        repo = QueueRepository(db)
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=threshold_sec)

        # 1. Fetch timed-out workers that are active
        stmt = select(AIWorker).where(
            AIWorker.heartbeat_at < cutoff,
            AIWorker.status != WorkerStatus.OFFLINE
        )
        res = await db.execute(stmt)
        dead_workers = res.scalars().all()

        recovered_jobs = []
        for worker in dead_workers:
            logger.warning(f"Worker {worker.worker_name} (ID: {worker.id}) missed heartbeat threshold. Offlining.")

            # Mark worker offline
            worker.status = WorkerStatus.OFFLINE
            worker.shutdown_reason = f"Heartbeat missed threshold {threshold_sec}s"

            # Check if it was running/dispatched a job lease
            if worker.current_job_id:
                job_id = worker.current_job_id
                job = await repo.get_job(job_id)
                # Requeue job (release lease and increment retry)
                if job and job.status in [AIJobStatus.DISPATCHED, AIJobStatus.RUNNING]:
                    logger.warning(f"Releasing lease for job {job_id} owned by crashed worker {worker.worker_name}")
                    stmt_job = update(AIJob).where(AIJob.id == job_id).values(
                        status=AIJobStatus.QUEUED,
                        worker_id=None,
                        lease_owner=None,
                        lease_expires_at=None,
                        retry_count=job.retry_count + 1
                    )
                    await db.execute(stmt_job)
                    await repo.requeue_job(job.queue_name.value, job_id, delay=0)
                    await repo.add_job_event(job_id, "job.created", {"recovery": True, "failed_worker": str(worker.id)})
                    recovered_jobs.append(job_id)

        await db.flush()
        return {
            "offlined_workers_count": len(dead_workers),
            "recovered_jobs_count": len(recovered_jobs),
            "recovered_job_ids": recovered_jobs
        }
