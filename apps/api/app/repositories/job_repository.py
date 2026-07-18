import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Any
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AIJobStatus, WorkerStatus, QueueType, JobFailureCategory
from app.models.ai_job import AIJob
from app.models.ai_job_result import AIJobResult, AIJobEvent
from app.models.ai_worker import AIWorker
from app.queue.redis_queue import RedisQueue


class QueueRepository:
    """Provides a data repository abstraction for job execution queues, workers, and results.

    ADR-019: Queue Abstraction, Idempotency checks, Lease-Based Ownership.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_job(self, job_id: uuid.UUID) -> Optional[AIJob]:
        stmt = select(AIJob).where(AIJob.id == job_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_job_by_idempotency_key(self, idempotency_key: str) -> Optional[AIJob]:
        stmt = select(AIJob).where(AIJob.idempotency_key == idempotency_key)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def create_job(
        self,
        org_id: uuid.UUID,
        job_type: str,
        priority: int,
        queue_name: QueueType,
        idempotency_key: Optional[str] = None,
        request_hash: Optional[str] = None,
        requested_by: Optional[uuid.UUID] = None,
        created_by: Optional[uuid.UUID] = None,
        source: str = "API"
    ) -> AIJob:
        # Enforce idempotency check before creating
        if idempotency_key:
            existing = await self.get_job_by_idempotency_key(idempotency_key)
            if existing:
                return existing

        job = AIJob(
            id=uuid.uuid4(),
            organization_id=org_id,
            job_type=job_type,
            status=AIJobStatus.QUEUED,
            priority=priority,
            queue_name=queue_name,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            requested_by=requested_by,
            created_by=created_by,
            source=source,
            retry_count=0,
            max_retries=3,
            retry_budget=3,
            retry_consumed=0,
            progress_percent=0.0,
            total_steps=6,
            current_step="Queued"
        )
        self.db.add(job)
        await self.db.flush()

        # Enqueue in low-level queue
        await self.enqueue_job(job.queue_name.value, job.id, job.priority, {"job_type": job_type})
        await self.add_job_event(job.id, "job.created", {"queue_name": queue_name.value})
        return job

    async def update_job_status(self, job_id: uuid.UUID, status: AIJobStatus) -> None:
        stmt = update(AIJob).where(AIJob.id == job_id).values(status=status)
        await self.db.execute(stmt)
        await self.db.flush()

    async def add_job_event(self, job_id: uuid.UUID, event: str, details: dict[str, Any]) -> None:
        evt = AIJobEvent(
            id=uuid.uuid4(),
            job_id=job_id,
            event=event,
            timestamp=datetime.now(timezone.utc),
            details_json=details
        )
        self.db.add(evt)
        await self.db.flush()

    async def save_result(
        self,
        job_id: uuid.UUID,
        status: AIJobStatus,
        output_json: dict[str, Any],
        error_message: Optional[str] = None,
        failure_reason: Optional[str] = None,
        failure_category: Optional[JobFailureCategory] = None,
        last_exception: Optional[str] = None,
        execution_time_ms: int = 0,
        token_usage: int = 0,
        cost: float = 0.0,
        retention_days: int = 7
    ) -> AIJobResult:
        result = AIJobResult(
            id=uuid.uuid4(),
            job_id=job_id,
            status=status,
            output_json=output_json,
            error_message=error_message,
            failure_reason=failure_reason,
            failure_category=failure_category,
            last_exception=last_exception,
            execution_time_ms=execution_time_ms,
            token_usage=token_usage,
            cost=cost,
            expires_at=datetime.now(timezone.utc) + timedelta(days=retention_days)
        )
        self.db.add(result)

        # Update job model
        stmt = update(AIJob).where(AIJob.id == job_id).values(
            status=status,
            completed_at=datetime.now(timezone.utc)
        )
        await self.db.execute(stmt)
        await self.db.flush()

        await self.add_job_event(job_id, "job.result.saved", {"result_id": str(result.id)})
        return result

    # ── Worker Management ──────────────────────────────────────────────────────

    async def register_worker(
        self,
        hostname: str,
        worker_name: str,
        supported_agents: list[str],
        supported_models: list[str],
        supported_tools: list[str],
        max_parallel_jobs: int = 1
    ) -> AIWorker:
        worker = AIWorker(
            id=uuid.uuid4(),
            hostname=hostname,
            worker_name=worker_name,
            status=WorkerStatus.IDLE,
            supported_agents={"list": supported_agents},
            supported_models={"list": supported_models},
            supported_tools={"list": supported_tools},
            max_parallel_jobs=max_parallel_jobs,
            last_started_at=datetime.now(timezone.utc),
            restart_count=0
        )
        self.db.add(worker)
        await self.db.flush()
        return worker

    async def update_worker_status(self, worker_id: uuid.UUID, status: WorkerStatus) -> None:
        stmt = update(AIWorker).where(AIWorker.id == worker_id).values(status=status)
        await self.db.execute(stmt)
        await self.db.flush()

    async def heartbeat_worker(
        self,
        worker_id: uuid.UUID,
        cpu_usage: float,
        memory_usage: float,
        running_jobs: int,
        queue_latency: float
    ) -> None:
        stmt = update(AIWorker).where(AIWorker.id == worker_id).values(
            heartbeat_at=datetime.now(timezone.utc),
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            running_jobs=running_jobs,
            queue_latency=queue_latency
        )
        await self.db.execute(stmt)
        await self.db.flush()

    # ── Queue Operations Wrapper ───────────────────────────────────────────────

    async def enqueue_job(self, queue_name: str, job_id: uuid.UUID, priority: int, data: dict[str, Any]) -> None:
        q = RedisQueue(queue_name)
        await q.enqueue(job_id, priority, data)

    async def dequeue_job(self, queue_name: str, visibility_timeout: int = 60) -> Optional[dict[str, Any]]:
        q = RedisQueue(queue_name)
        return await q.dequeue(visibility_timeout)

    async def ack_job(self, queue_name: str, job_id: uuid.UUID) -> bool:
        q = RedisQueue(queue_name)
        return await q.acknowledge(job_id)

    async def requeue_job(self, queue_name: str, job_id: uuid.UUID, delay: int = 0) -> bool:
        q = RedisQueue(queue_name)
        return await q.requeue(job_id, delay)
