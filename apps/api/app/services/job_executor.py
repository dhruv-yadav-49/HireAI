import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import JobType
from app.models.scheduled_job import ScheduledJob
from app.services.reminder_engine import ReminderEngine
from app.services.notification_engine import NotificationEngine

logger = logging.getLogger(__name__)


class JobExecutor:
    """Dispatches scheduled jobs to their respective domain service engines and tracks execution run metrics."""

    @staticmethod
    async def execute_job(db: AsyncSession, job: ScheduledJob) -> dict[str, int]:
        """Main dispatcher entrypoint."""
        job_type = job.job_type
        logger.info(f"Starting Job Execution dispatcher: JobID={job.id}, Type={job_type.value}")

        metrics = {
            "processed_records": 0,
            "created_reminders": 0,
            "published_events": 0,
            "queued_notifications": 0,
        }

        if job_type == JobType.GENERATE_REMINDERS:
            # 1. Sweep to generate pending inactivity, due tasks, or follow-up reminders
            results = await ReminderEngine.generate_reminders(db, job.organization_id)
            reminders_created = sum(results.values())
            
            metrics["created_reminders"] = reminders_created
            metrics["processed_records"] = reminders_created

        elif job_type == JobType.PROCESS_REMINDERS:
            # 2. Sweep to dispatch due reminders as domain events
            results = await ReminderEngine.process_reminders(db, job.organization_id)
            processed = results.get("reminders_processed", 0)
            
            metrics["published_events"] = processed
            metrics["processed_records"] = processed

        elif job_type == JobType.SEND_QUEUED_NOTIFICATIONS:
            # 3. Sweep to dispatch queued emails, SMS, or WhatsApp alerts
            results = await NotificationEngine.send_queued_notifications(db, job.organization_id)
            sent = results.get("notifications_sent", 0)
            failed = results.get("notifications_failed", 0)
            total = sent + failed
            
            metrics["queued_notifications"] = total
            metrics["processed_records"] = total

        elif job_type == JobType.SYSTEM_PRUNE_LOGS:
            # 4. Mock system cleanup sweep
            logger.info("SYSTEM_PRUNE_LOGS: Executed mock log pruning sweep.")
            metrics["processed_records"] = 10  # Mock value

        else:
            logger.error(f"Unsupported job type: {job_type.value}")
            raise NotImplementedError(f"Job execution handler not implemented for type: {job_type.value}")

        logger.info(
            f"Finished Job Execution: JobID={job.id}, Metrics={metrics}"
        )
        return metrics
