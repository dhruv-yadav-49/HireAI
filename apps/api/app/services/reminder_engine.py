import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import DomainEvent, get_event_publisher
from app.models.enums import (
    ActorType,
    EntityType,
    ReminderStatus,
    ReminderType,
    TaskStatus,
)
from app.models.lead import Lead
from app.models.task import Task
from app.models.scheduled_job import Reminder


class ReminderEngine:
    """Core domain engine for generating and processing CRM time-based reminders."""

    @staticmethod
    async def _try_insert_reminder(db: AsyncSession, reminder: Reminder) -> bool:
        """Attempts to insert a reminder; returns True on success, False on duplicate."""
        try:
            db.add(reminder)
            await db.flush()  # Flush to DB immediately to trigger unique constraint
            return True
        except IntegrityError:
            await db.rollback()
            return False

    @staticmethod
    async def generate_reminders(
        db: AsyncSession, organization_id: Optional[uuid.UUID] = None
    ) -> dict[str, int]:
        """Scans active leads and tasks to generate pending reminders."""
        now = datetime.now(timezone.utc)
        metrics = {"inactivity_reminders": 0, "due_task_reminders": 0, "followup_reminders": 0}

        # 1. Lead Inactivity (7 Days)
        inactivity_threshold = now - timedelta(days=7)
        lead_stmt = select(Lead).where(
            Lead.deleted_at.is_(None),
            Lead.last_activity_at <= inactivity_threshold,
        )
        if organization_id:
            lead_stmt = lead_stmt.where(Lead.organization_id == organization_id)

        leads_res = await db.execute(lead_stmt)
        inactive_leads = leads_res.scalars().all()

        for lead in inactive_leads:
            reminder = Reminder(
                organization_id=lead.organization_id,
                entity_type=EntityType.LEAD,
                entity_id=lead.id,
                reminder_type=ReminderType.INACTIVITY,
                remind_at=now,
                status=ReminderStatus.PENDING,
                created_by_type=ActorType.SYSTEM,
            )
            inserted = await ReminderEngine._try_insert_reminder(db, reminder)
            if inserted:
                metrics["inactivity_reminders"] += 1

        # 2. Due Tasks (Within 1 Hour)
        due_threshold = now + timedelta(hours=1)
        task_stmt = select(Task).where(
            Task.deleted_at.is_(None),
            Task.status.in_([TaskStatus.OPEN, TaskStatus.IN_PROGRESS]),
            Task.due_at.isnot(None),
            Task.due_at >= now,
            Task.due_at <= due_threshold,
        )
        if organization_id:
            task_stmt = task_stmt.where(Task.organization_id == organization_id)

        tasks_res = await db.execute(task_stmt)
        due_tasks = tasks_res.scalars().all()

        for task in due_tasks:
            remind_time = max(now, task.due_at - timedelta(hours=1))
            reminder = Reminder(
                organization_id=task.organization_id,
                entity_type=EntityType.TASK,
                entity_id=task.id,
                reminder_type=ReminderType.DUE_TASK,
                remind_at=remind_time,
                status=ReminderStatus.PENDING,
                created_by_type=ActorType.SYSTEM,
            )
            inserted = await ReminderEngine._try_insert_reminder(db, reminder)
            if inserted:
                metrics["due_task_reminders"] += 1

        # 3. Follow-up Reminders (Lead created 2 days ago without any tasks)
        followup_threshold = now - timedelta(days=2)
        lead_created_stmt = select(Lead).where(
            Lead.deleted_at.is_(None),
            Lead.created_at <= followup_threshold,
        )
        if organization_id:
            lead_created_stmt = lead_created_stmt.where(Lead.organization_id == organization_id)

        leads_created_res = await db.execute(lead_created_stmt)
        old_leads = leads_created_res.scalars().all()

        for lead in old_leads:
            # Check if any task exists for this lead
            task_check_stmt = select(Task.id).where(
                Task.lead_id == lead.id,
                Task.deleted_at.is_(None),
            )
            task_check_res = await db.execute(task_check_stmt)
            if task_check_res.first() is None:
                reminder = Reminder(
                    organization_id=lead.organization_id,
                    entity_type=EntityType.LEAD,
                    entity_id=lead.id,
                    reminder_type=ReminderType.FOLLOW_UP,
                    remind_at=now,
                    status=ReminderStatus.PENDING,
                    created_by_type=ActorType.SYSTEM,
                )
                inserted = await ReminderEngine._try_insert_reminder(db, reminder)
                if inserted:
                    metrics["followup_reminders"] += 1

        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
        return metrics


    @staticmethod
    async def process_reminders(
        db: AsyncSession, organization_id: Optional[uuid.UUID] = None
    ) -> dict[str, int]:
        """Dispatches due reminders by publishing domain events."""
        now = datetime.now(timezone.utc)
        metrics = {"reminders_processed": 0}

        stmt = select(Reminder).where(
            Reminder.status == ReminderStatus.PENDING,
            Reminder.remind_at <= now,
        )
        if organization_id:
            stmt = stmt.where(Reminder.organization_id == organization_id)

        res = await db.execute(stmt)
        due_reminders = res.scalars().all()

        publisher = get_event_publisher()

        for reminder in due_reminders:
            # 1. Map reminder type to standard domain event names
            if reminder.reminder_type == ReminderType.INACTIVITY:
                event_name = "lead.inactive"
                payload = {"lead_id": str(reminder.entity_id), "reminder_id": str(reminder.id)}
            elif reminder.reminder_type == ReminderType.DUE_TASK:
                event_name = "task.due_soon"
                payload = {"task_id": str(reminder.entity_id), "reminder_id": str(reminder.id)}
            elif reminder.reminder_type == ReminderType.FOLLOW_UP:
                event_name = "lead.followup_due"
                payload = {"lead_id": str(reminder.entity_id), "reminder_id": str(reminder.id)}
            else:
                continue

            # 2. Update status to dispatched
            reminder.status = ReminderStatus.DISPATCHED
            reminder.updated_at = now
            db.add(reminder)

            # 3. Publish domain event
            event = DomainEvent(
                event_name=event_name,
                tenant_id=reminder.organization_id,
                event_id=uuid.uuid4(),
                payload=payload,
                event_version=1,
            )
            await publisher.publish(event)
            metrics["reminders_processed"] += 1

        await db.commit()
        return metrics
