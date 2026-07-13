# ADR-008: Scheduler & Reminder Engine

**Status**: Accepted  
**Date**: 2026-07-13  
**Sprint**: 4B  

---

## Context

We require a scheduling and reminder mechanism to make HireAI time-aware. The system must support:
1. Automated background tasks (e.g. log cleanups, system checkups).
2. Generating time-based reminders for CRM entities (e.g. Lead inactivity for 7 days, task due in 1 hour).
3. Processing and executing scheduled events, dispatching notification emails/messages.
4. Correct timezone handling based on the tenant's organization settings.
5. High reliability with retry configurations, error logging, and dead-letter queues.
6. Execution concurrency safety to prevent double execution when running multiple backend instances.

---

## Decision

We have established the following design principles for the Scheduler & Reminder Engine:

### 1. In-Process Polling and Database Row Locking
- **In-Process Ticker (Why Polling / Why No Celery?)**: We run a background async loop in FastAPI that ticks every 60 seconds (controlled via `SCHEDULER_POLL_INTERVAL_SECONDS` config). This avoids introducing heavy external dependencies (Celery, Redis, RabbitMQ, or Temporal) for the initial MVP, keeping local deployments fast and simple.
- **Concurrency Safety**: To prevent multiple scheduler instances from executing the same job simultaneously, the tick uses PostgreSQL row-level locking:
  ```sql
  SELECT * FROM scheduled_jobs 
  WHERE next_run_at <= NOW() AND status = 'ACTIVE'
  FOR UPDATE SKIP LOCKED
  ```
  This ensures that only one worker node locks and executes a scheduled job, making the system horizontally scalable.

### 2. Timezone-Aware Cron Calculations
- **Storage**: All database timestamps (`next_run_at`, `last_run_at`, `remind_at`) are stored in UTC.
- **Conversion**: Cron intervals are parsed using `croniter`. The execution time is calculated in the organization's configured timezone (retrieved from `organizations.timezone`) and converted back to UTC for database comparison.
- **Timezone Validation**: A strict Pydantic model validator validates timezone names against the IANA database using Python's `zoneinfo.available_timezones()`.
- **Cron Validation**: A strict Pydantic model validator uses `croniter.is_valid()` to verify cron syntax before writing to the database.

### 3. Decoupled Reminder & Notification Pipelines
- **Reminder Generation**: A recurring scheduled job `GENERATE_REMINDERS` scans leads and tasks to insert due/upcoming `Reminder` records in the database.
- **Deduplication**: To prevent duplicate reminder creation (e.g. multiple inactivity events for the same lead), a partial unique index is added on `(organization_id, entity_type, entity_id, reminder_type)` restricted to `status = 'PENDING'`. Only one active reminder can exist per target.
- **Reminder Processing**: Another recurring job `PROCESS_REMINDERS` fetches pending reminders where `remind_at <= NOW()`, marks them as `DISPATCHED`, and publishes corresponding `DomainEvent` objects (e.g., `lead.inactive` or `task.due_soon`).
- **Separation of Concerns Constraint**: The Scheduler never modifies Leads or Tasks directly. It only publishes Events, which the `WorkflowEngine` captures to execute workflows (e.g., creating tasks, modifying statuses). The Scheduler remains a pure time trigger.
- **Notification Queue**: Communication actions (e.g. send email/WhatsApp) are written to a `notification_queue` table with an `idempotency_key` constraint to prevent duplicate sends. A background job processes this queue asynchronously.
- **Observation Metrics**: Every job execution records duration, processed rows count, and created reminders/notifications metrics.

### 4. Strong Database Types (Enums)
- **ReminderType**: Implemented as native Postgres enum (`INACTIVITY`, `DUE_TASK`, `FOLLOW_UP`, `BIRTHDAY`) to prevent spelling errors.
- **EntityType**: Implemented as native Postgres enum (`LEAD`, `TASK`) for domain-level integrity.
- **NotificationProvider**: Optional enum (`SMTP`, `SES`, `SENDGRID`, `TWILIO`, `META`, `GUPSHUP`) representing targeted communication channels.
- **Notification Priority & Expiration**: Queue alerts support priorities (`LOW`, `NORMAL`, `HIGH`, `URGENT`) and expiration limits (`expires_at`) to drop obsolete notifications.

---

## Future Evolution

As the platform scales to millions of tenants and high-volume background workflows, we plan to evolve the scheduler:
1. **Redis Streams / BullMQ**: Transition from DB polling to an in-memory queue.
2. **Temporal**: Leverage Temporal.io orchestration engine for resilient, long-running workflows, automated retries, and distributed state management.
3. **Kafka**: Use Kafka for high-throughput distributed event streaming.

---

## Consequences

- **Observable execution history**: Every scheduled job tick produces detailed log records (`job_executions`) containing a snapshot of its payload, duration metrics, and execution node details.
- **Fully integrated CRM**: Reminders naturally trigger standard workflow rules, reusing condition validations and action registries.
- **Low infrastructure footprint**: Avoids the need for external tools (Celery, Redis, Cron daemons) for MVP deployment.
