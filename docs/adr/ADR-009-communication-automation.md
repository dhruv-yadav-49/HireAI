# ADR-009: Communication Automation Foundation

**Status**: Accepted  
**Date**: 2026-07-13  
**Sprint**: 4C  

---

## Context

We require a resilient, multi-tenant communication layer to manage all outgoing and incoming communications (Email, WhatsApp, and SMS) for HireAI. The engine must support:
1. Unified communication abstractions for multi-channel messaging (no direct provider coupling).
2. Dynamic templating with validation at creation and rendering phases.
3. Concurrency-safe and idempotent outgoing communications.
4. Threaded conversation logs to support future AI replies and conversation context analysis (Sprint 5).
5. Append-only timeline delivery audit tracking.
6. Robust retry policies with progressive backoff intervals.

---

## Decision

We have established the following design decisions for the Communication Automation layer:

### 1. Provider Abstraction & Capability Contract
- **Base Interface**: All provider connectors inherit from a standard, future-ready `CommunicationProvider` protocol, defining `validate()`, `health_check()`, `send()`, `get_delivery_status()`, `cancel()`, and `parse_webhook()`.
- **Capability Flags**: Providers declare capabilities inside `capabilities_json` (e.g. `supports_attachments`, `supports_html`). The dispatcher performs runtime capability validation checks before attempting delivery.

### 2. Multi-Tenant Template Engine & Variable Registry
- **Dual-Phase Validation**:
  - *Creation time*: The engine parses template body/subjects, extracts variables, and registers them in `variables_json`.
  - *Render time*: Matches required variables against lead/task/user context, throwing a `ValidationException` on missing placeholders.
- **Render Versioning**: Tracks `render_engine_version` (default 1) in database records, ensuring backward-compatibility as rendering specs evolve.

### 3. Immutable Rendered Snapshots
- Once rendered and queued, the raw body/subject, fully rendered body/subject, and an exact snapshot of the template configuration are stored permanently inside the `communications` record. This guarantees that future modifications to the template text do not corrupt historic records.

### 4. Conversation Threading & Direction
- **Bidirectional Log**: Outbound and inbound messages are recorded in the same `communications` table, differentiated by the `direction` enum (`OUTBOUND`, `INBOUND`).
- **Threading**: Conversations are logically grouped using a `conversation_id` UUID and an optional `parent_communication_id` to establish threaded hierarchies.

### 5. Append-Only Delivery Event Logging
- Every communication lifecycle transition (queued, processing, sent, delivered, read, failed, bounced, unsubscribed) appends an event to the `communication_deliveries` audit table.
- Events are ordered chronologically using a non-nullable integer `sequence_no` to protect timeline ordering against out-of-order webhook callbacks.

### 6. Event-Driven Lifecycle Publishing
- The communication engine operates as a domain event producer, publishing events (e.g. `communication.created`, `communication.sent`, `communication.delivered`, `communication.read`, `communication.failed`) upon delivery transitions. This allows AI Sales Executives and other asynchronous handlers in Sprint 5 to react to events without direct coupling.

### 7. Progressive Retry Delays
- Failed dispatches schedule retries with progressive backoff delays:
  - Attempt 1: 5 seconds
  - Attempt 2: 30 seconds
  - Attempt 3: 120 seconds
  - Attempt 4: 600 seconds
- If failure persists after 4 attempts, the message status is permanently marked as `FAILED`.

---

## Consequences

- **AI Readiness**: Sprint 5 (AI Sales Executive) interacts only with `CommunicationService` via event streams, decoupled from provider SDKs.
- **Auditability**: Complete messaging history is immutable, with structured latency, error codes, and vendor-response fields for delivery analytics.
- **Isolation**: Tenant scopes are strictly isolated at templates, providers, and communications table levels.
