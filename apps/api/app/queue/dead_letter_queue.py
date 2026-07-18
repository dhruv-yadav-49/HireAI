from __future__ import annotations
import uuid
import logging
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AIJobStatus, QueueType, JobFailureCategory
from app.models.ai_job import AIJob
from app.repositories.job_repository import QueueRepository

logger = logging.getLogger(__name__)


class DeadLetterQueue:
    """Manages manual replays and investigations for exhausted/failed executions.

    CTO refinement #8: DLQ categorization.
    """

    @classmethod
    async def route_to_dlq(
        cls,
        db: AsyncSession,
        job_id: uuid.UUID,
        failure_reason: str,
        category: JobFailureCategory,
        last_exception: Optional[str] = None
    ) -> None:
        """Explicitly routes a failed job to DLQ database state."""
        repo = QueueRepository(db)
        stmt = update(AIJob).where(AIJob.id == job_id).values(
            status=AIJobStatus.DEAD_LETTER,
            queue_name=QueueType.DEAD_LETTER
        )
        await db.execute(stmt)
        await db.flush()

        # Save result with DLQ categorizations (CTO refinement #8)
        await repo.save_result(
            job_id=job_id,
            status=AIJobStatus.DEAD_LETTER,
            output_json={},
            error_message=failure_reason,
            failure_reason=failure_reason,
            failure_category=category,
            last_exception=last_exception
        )
        await repo.add_job_event(job_id, "job.dead_lettered", {"category": category.value})
        logger.warning(f"Routed job {job_id} to Dead Letter Queue. Category: {category}")

    @classmethod
    async def replay_job(cls, db: AsyncSession, job_id: uuid.UUID) -> bool:
        """Replays/resubmits a dead lettered job back to the active queue."""
        repo = QueueRepository(db)
        job = await repo.get_job(job_id)
        if not job or job.status != AIJobStatus.DEAD_LETTER:
            logger.warning(f"Cannot replay job {job_id}. Invalid job or state: {job.status if job else 'None'}")
            return False

        # Reset retry metrics
        stmt = update(AIJob).where(AIJob.id == job_id).values(
            status=AIJobStatus.QUEUED,
            queue_name=QueueType.DEFAULT,
            retry_count=0,
            retry_consumed=0
        )
        await db.execute(stmt)
        await db.flush()

        # Remove from DEAD_LETTER and enqueue back to DEFAULT
        await repo.ack_job("DEAD_LETTER", job_id)
        await repo.enqueue_job("DEFAULT", job_id, job.priority, {"replayed": True})
        await repo.add_job_event(job_id, "job.created", {"replay": True})
        logger.info(f"Successfully replayed job {job_id} from DLQ back to active execution queue.")
        return True
