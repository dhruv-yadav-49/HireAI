from __future__ import annotations
import random
import logging
import uuid
from typing import Optional
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AIJobStatus, RetryStrategy, QueueType
from app.models.ai_job import AIJob
from app.repositories.job_repository import QueueRepository

logger = logging.getLogger(__name__)


class RetryManager:
    """Manages scheduling and delay computations for failed execution jobs.

    CTO refinement #7: Jitter implementation.
    """

    @classmethod
    async def process_failure(
        cls,
        db: AsyncSession,
        job_id: uuid.UUID,
        strategy: RetryStrategy = RetryStrategy.JITTER
    ) -> Optional[int]:
        """Calculates delay seconds for a job. Returns None if max retries exceeded (sends to DLQ)."""
        repo = QueueRepository(db)
        job = await repo.get_job(job_id)
        if not job:
            return None

        # Check retry limit
        if job.retry_count >= job.max_retries:
            logger.warning(f"Job {job_id} reached maximum retries limit ({job.max_retries}). Forwarding to DLQ.")
            # Move status to DEAD_LETTER in DB
            stmt = update(AIJob).where(AIJob.id == job.id).values(
                status=AIJobStatus.DEAD_LETTER,
                queue_name=QueueType.DEAD_LETTER
            )
            await db.execute(stmt)
            await db.flush()

            # Dequeue from current queue and enqueue into DEAD_LETTER queue
            await repo.ack_job(job.queue_name.value, job.id)
            await repo.enqueue_job("DEAD_LETTER", job.id, job.priority, {"failed": True})
            await repo.add_job_event(job.id, "job.dead_lettered", {"retry_count": job.retry_count})
            return None

        # Calculate retry delay based on strategy
        delay = 2  # default
        retry_num = job.retry_count + 1

        if strategy == RetryStrategy.FIXED_DELAY:
            delay = 3
        elif strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = 2 ** retry_num
        elif strategy == RetryStrategy.JITTER:
            # Base exponential + randomized jitter (CTO refinement #7)
            base = 2 ** retry_num
            jitter = random.uniform(0.1, 1.0)
            delay = int(base + jitter)

        # Update retry counts in DB
        stmt = update(AIJob).where(AIJob.id == job.id).values(
            retry_count=retry_num,
            retry_consumed=retry_num,
            status=AIJobStatus.RETRYING,
            queue_name=QueueType.RETRY
        )
        await db.execute(stmt)
        await db.flush()

        # Re-enqueue in RETRY queue with calculated delay
        await repo.ack_job(job.queue_name.value, job.id)
        await repo.enqueue_job("RETRY", job.id, job.priority, {"retry_num": retry_num})
        await repo.add_job_event(job.id, "job.retried", {"delay_sec": delay, "retry_count": retry_num})

        return delay
