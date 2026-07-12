# ADR-006: Task Domain Design & Timeline Evolution Rules

**Status**: Accepted  
**Date**: 2026-07-12  
**Sprint**: 3B

---

## Context

Task and Follow-up Management represents the execution layer for future automated features (email/WhatsApp automation, AI scheduling, calendar syncs). We require a production-grade, multi-tenant schema that remains resilient under high concurrency and allows downstream AI systems to consume timeline metadata reliably.

## Decision

We have established five design rules for the Task domain:

### 1. Mandated Lead Scope (No Polymorphic Tasks MVP)
- Tasks are restricted strictly to `leads` (`lead_id` NOT NULL FK).
- Generically polymorphic task associations (e.g. `entity_type`, `entity_id` supporting Deals/Tickets/Accounts) are deferred to future sprints. This keeps referential integrity strong and query patterns simple.

### 2. Computed `is_overdue` Boolean
- The database status column remains a clean state representation: `OPEN`, `IN_PROGRESS`, `COMPLETED`, or `CANCELLED`.
- We do **NOT** use `OVERDUE` as an enum status in the database.
- Instead, `is_overdue: bool` is calculated dynamically at query-time in the Pydantic serialization layer based on `due_at < NOW()`. This ensures robust progressive transition checks (e.g., `OPEN` -> `COMPLETED` can occur naturally even if the task is overdue).

### 3. Soft Delete Cascade
- When a Lead is soft-deleted, the related Tasks are soft-deleted by setting `deleted_at = now`.
- Crucially, related timeline logs (`task_activities` and `lead_activities`) remain unchanged (append-only timeline history rule is preserved).

### 4. Automated `last_activity_at` Bumps
- Every meaningful change to a Task (creation, status update, assignment, reminder change, completion) automatically bumps `last_activity_at = NOW()` in the database. This allows high-performance sorting for dashboard lists (e.g., "Recently Active Tasks") without complex query joins.

### 5. Timeline Metadata Evolution Contract (`metadata_version`)
To support future AI-agent parsing of timeline logs, metadata structure changes must follow these evolution rules:
- **Rule 5.1 (No Key Overwrite)**: A key once introduced inside `event_metadata` JSON cannot be redefined or changed in type.
- **Rule 5.2 (Increment Version)**: If new metadata keys are introduced to support advanced properties (e.g., adding `ai_confidence` or `escalated_by`), the `metadata_version` must be incremented. Parsers can switch on this version.
- **Rule 5.3 (Request ID)**: Every activity must log `request_id` from the request context to correlate frontend requests with backend database events.

---

## Consequences

- Stable progression transitions without overdue status interference.
- Simple, high-performance database queries filtering strictly on `ctx.tenant_id`.
- Predictable timeline metadata for AI parsers.
