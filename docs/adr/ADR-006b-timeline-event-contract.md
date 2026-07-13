# ADR-006b: Universal Timeline Event Contract & Domain Event Publisher

**Status**: Accepted  
**Date**: 2026-07-12  
**Sprint**: 3B

---

## Context

As HireAI grows from a CRUD system to an AI-first CRM, multiple downstream services (automation engines, SMS/Email connectors, SLA trackers, webhook dispatchers, and AI Sales agents) will need to react to state changes in real time.
To facilitate this safely without tightly coupling domain services to external integrations, we need to standardize the timeline data models and introduce a loose domain event publisher abstraction.

## Decision

We have established three critical architectural boundaries:

### 1. ActorType core enum
All timelines and audit logs must capture the action initiator. We reuse the global core `ActorType` enum:
- `USER`
- `SYSTEM`
- `AI`
- `WEBHOOK`

### 2. Universal Timeline Event Schema Contract
Every historical activity log model (`lead_activities`, `task_activities`, and all future timelines) must follow a unified database schema shape:
- `id` (UUID Primary Key)
- `parent_id` (UUID Foreign Key of the target object)
- `actor_id` (UUID Foreign Key of User, nullable)
- `actor_type` (Enum `ActorType`)
- `activity_type` (Enum representing action like status, assignment, note, etc.)
- `event_metadata` (JSONB containing metadata, including the client's `request_id`)
- `metadata_version` (SmallInt representing metadata structure version, allowing schemas to evolve backward-compatibly)
- `created_at` (Timestamp defaults to `NOW()`)

### 3. Abstract Domain Event Publisher
We introduced a simple, asynchronous `DomainEventPublisher` interface (`Protocol`) inside `app/core/events.py` mapping:
```python
class DomainEventPublisher(Protocol):
    async def publish(self, event: DomainEvent) -> None:
        ...
```
- Core business services (`LeadService` and `TaskService`) formulate and dispatch `DomainEvent` objects containing payload details on creations, updates, and soft deletions.
- Initially, we register a `NoOpEventPublisher` for Sprint 3. The actual implementation can be swapped to Redis Streams, RabbitMQ, or AWS EventBridge in Sprint 6 without modifying any Service code.

---

## Consequences

- **100% Extensible Automation**: Webhook services and Reminders can list event subscriptions simply by listening to publisher dispatches.
- **Unified Timeline Consumption**: Downstream AI models parse timelines reliably since all activities follow the exact same properties.
- **Traceability**: Audits are fully traceable from HTTP requests down to DB timelines by correlating `request_id` values.
