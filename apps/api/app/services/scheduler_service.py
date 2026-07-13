import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionFactory
from app.models.enums import JobExecutionStatus, JobStatus
from app.models.organization import Organization
from app.models.scheduled_job import JobExecution, ScheduledJob
from app.services.cron_service import CronService
from app.services.job_executor import JobExecutor

logger = logging.getLogger(__name__)


class SchedulerService:
    """Core multi-tenant Scheduler Engine with row-locking concurrency controls."""

    @staticmethod
    async def start_polling():
        """FastAPI background loop runner ticking at config intervals."""
        poll_interval = getattr(settings, "SCHEDULER_POLL_INTERVAL_SECONDS", 60)
        logger.info(f"Background Scheduler starting. Polling interval: {poll_interval}s")

        while True:
            try:
                # Open isolated db session per tick
                async with AsyncSessionFactory() as db:
                    await SchedulerService.tick(db)
            except asyncio.CancelledError:
                logger.info("Background Scheduler cancelled.")
                break
            except Exception as e:
                logger.error(f"Scheduler tick unhandled error: {str(e)}")

            await asyncio.sleep(poll_interval)

    @staticmethod
    async def tick(db: AsyncSession):
        """Scans due active jobs, locking them, calculating schedules, and dispatching runs."""
        now = datetime.now(timezone.utc)

        # 1. Query due active jobs with SELECT FOR UPDATE SKIP LOCKED
        stmt = (
            select(ScheduledJob)
            .where(
                ScheduledJob.next_run_at <= now,
                ScheduledJob.status == JobStatus.ACTIVE,
            )
            .with_for_update(skip_locked=True)
        )
        res = await db.execute(stmt)
        due_jobs = res.scalars().all()

        if not due_jobs:
            return

        logger.info(f"Scheduler tick: Locked {len(due_jobs)} due jobs for execution.")

        for job in due_jobs:
            # 2. Idempotency execution key
            execution_key = str(int(job.next_run_at.timestamp()))

            # Verify no run exists for this key
            dup_stmt = select(JobExecution).where(
                JobExecution.job_id == job.id,
                JobExecution.execution_key == execution_key,
            )
            dup_res = await db.execute(dup_stmt)
            if dup_res.scalar() is not None:
                # Skip duplicate run
                continue

            # 3. Resolve timezone settings
            org_tz = "UTC"
            if job.organization_id:
                org_stmt = select(Organization).where(Organization.id == job.organization_id)
                org_res = await db.execute(org_stmt)
                org = org_res.scalar()
                if org and org.timezone:
                    org_tz = org.timezone
            job_tz = job.timezone or org_tz

            # 4. Calculate next run schedule
            try:
                next_run = CronService.get_next_run(job.cron_expression, job.next_run_at, job_tz)
            except Exception as cron_exc:
                logger.error(f"Cron next run calculation failed for Job={job.id}: {cron_exc}")
                # Fallback next run in 1 hour if calculations crash
                next_run = now + timedelta(hours=1)

            # 5. Log JobExecution status as RUNNING
            instance_id = f"hireai-api-{uuid.uuid4().hex[:6]}"
            execution = JobExecution(
                job_id=job.id,
                organization_id=job.organization_id,
                status=JobExecutionStatus.RUNNING,
                execution_key=execution_key,
                attempt=job.retry_count + 1,
                payload_snapshot=job.payload,
                scheduler_instance=instance_id,
                started_at=now,
            )
            db.add(execution)

            # Update job next schedule slot
            job.last_run_at = job.next_run_at
            job.next_run_at = next_run
            db.add(job)

            # Commit updates immediately so other tick nodes do not see the locked slot
            await db.commit()

            # 6. Execute Job
            try:
                metrics = await JobExecutor.execute_job(db, job)

                # Update execution logs as SUCCESS
                execution.status = JobExecutionStatus.SUCCESS
                execution.finished_at = datetime.now(timezone.utc)
                execution.duration_ms = int(
                    (execution.finished_at - execution.started_at).total_seconds() * 1000
                )
                execution.processed_records = metrics.get("processed_records", 0)
                execution.created_reminders = metrics.get("created_reminders", 0)
                execution.published_events = metrics.get("published_events", 0)
                execution.queued_notifications = metrics.get("queued_notifications", 0)

                # Reset retry count on success
                job.retry_count = 0
                db.add(execution)
                db.add(job)
                await db.commit()

            except Exception as run_exc:
                # Update retry counts
                job.retry_count += 1
                execution.finished_at = datetime.now(timezone.utc)
                execution.duration_ms = int(
                    (execution.finished_at - execution.started_at).total_seconds() * 1000
                )
                execution.error_message = str(run_exc)

                if job.retry_count >= job.max_retries:
                    # Mark DEAD_LETTER and disable job
                    execution.status = JobExecutionStatus.DEAD_LETTER
                    job.status = JobStatus.DISABLED
                    logger.error(
                        f"Scheduled Job exceeded max retries. Dead-lettered and disabled: "
                        f"JobID={job.id}, Error={run_exc}"
                    )
                else:
                    execution.status = JobExecutionStatus.RETRYING
                    # Calculate backoff retry: 60s * 2^retry
                    backoff_delay = min(3600, 60 * (2 ** job.retry_count))
                    job.next_run_at = now + timedelta(seconds=backoff_delay)
                    logger.warning(
                        f"Job execution failed. Rescheduling retry in {backoff_delay}s: "
                        f"JobID={job.id}, Error={run_exc}"
                    )

                db.add(execution)
                db.add(job)
                await db.commit()
