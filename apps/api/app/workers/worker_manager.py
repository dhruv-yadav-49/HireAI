from __future__ import annotations
import uuid
import logging
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import WorkerStatus
from app.models.ai_worker import AIWorker
from app.repositories.job_repository import QueueRepository

logger = logging.getLogger(__name__)


class WorkerManager:
    """Manages worker startup, heartbeat telemetry, draining, and clean deregistration loops.

    CTO refinement #10: DRAINING worker state support.
    """

    @classmethod
    async def register(
        cls,
        db: AsyncSession,
        hostname: str,
        worker_name: str,
        supported_agents: list[str],
        supported_models: list[str],
        supported_tools: list[str],
        max_parallel_jobs: int = 1
    ) -> AIWorker:
        """Saves a new worker record in the active database registry."""
        repo = QueueRepository(db)
        worker = await repo.register_worker(
            hostname=hostname,
            worker_name=worker_name,
            supported_agents=supported_agents,
            supported_models=supported_models,
            supported_tools=supported_tools,
            max_parallel_jobs=max_parallel_jobs
        )
        logger.info(f"Registered worker process {worker_name} on host {hostname}")
        return worker

    @classmethod
    async def heartbeat(
        cls,
        db: AsyncSession,
        worker_id: uuid.UUID,
        cpu_usage: float = 5.0,
        memory_usage: float = 12.0,
        running_jobs: int = 0,
        queue_latency: float = 0.01
    ) -> None:
        """Pushes performance metrics and timestamps a heartbeat event."""
        repo = QueueRepository(db)
        await repo.heartbeat_worker(
            worker_id=worker_id,
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            running_jobs=running_jobs,
            queue_latency=queue_latency
        )

    @classmethod
    async def drain(cls, db: AsyncSession, worker_id: uuid.UUID) -> None:
        """Transitions worker status to DRAINING. Draining nodes reject new queue dequeues."""
        repo = QueueRepository(db)
        await repo.update_worker_status(worker_id, WorkerStatus.DRAINING)
        logger.info(f"Worker {worker_id} set to DRAINING status.")

    @classmethod
    async def offline(cls, db: AsyncSession, worker_id: uuid.UUID, reason: str = "Graceful shutdown") -> None:
        """Marks worker status as OFFLINE."""
        stmt = update(AIWorker).where(AIWorker.id == worker_id).values(
            status=WorkerStatus.OFFLINE,
            shutdown_reason=reason
        )
        await db.execute(stmt)
        await db.flush()
        logger.info(f"Worker {worker_id} is now OFFLINE. Reason: {reason}")
