# ADR-005: Lead Domain Design & Business Pipeline Controls

**Status**: Accepted  
**Date**: 2026-07-12  
**Sprint**: 3A

---

## Context

We are introducing the core `leads` table and its support schemas (`lead_notes`, `lead_tags`, `lead_tag_assignments`, and `lead_activities`). 
Since the Lead entity represents the canonical business object that all future CRM connectors, CSV uploaders, email services, and AI Sales Executives will interact with, it must be highly secure under concurrent workflows, multi-tenant boundaries, and automated parsing.

## Decision

We have established five fundamental guardrails for the Lead domain:

### 1. Concurrency-Safe Sequential Lead Numbers (`lead_number`)
Instead of using unsafe `SELECT MAX(lead_number) + 1` queries which collide under parallel user actions, we introduced an `organization_sequences` table.
- Every new lead creation locks the sequence row using `SELECT ... FOR UPDATE` (or inserts the first sequence of `1001` if it is a brownfield tenant).
- The value is incremented atomically inside the same transaction block, ensuring 100% collision-safe incrementing numbers per organization.

### 2. Version-Based Optimistic Locking (`version`)
To prevent concurrent salesperson edits from blindly overwriting one another (e.g. Salesperson A and B editing status/notes at the same time), every update request requires the lead's read `version`.
- The update query filters on `WHERE id = :id AND version = :current_version`.
- If another process updated the version in the database, the query updates 0 rows, triggering a `ConcurrentUpdateException` (HTTP 409 Conflict) instead of overwriting.

### 3. Append-Only activity logs (`lead_activities`)
The activity timeline represents the audit trail for every action occurring on a lead.
- The `LeadActivityRepository` and `LeadService` contain **no update or delete APIs**.
- It is strictly append-only.
- Activities include `ActorType` (USER, SYSTEM, AI, WEBHOOK) and `CreatedSource` (MANUAL_UI, CSV_IMPORT, API, WEBHOOK, AI_AGENT) for downstream AI analytics.

### 4. Rigid Status Transition Engine
Leads progress through a strict pipeline state machine:
- `NEW` -> `CONTACTED` -> `MEETING_SCHEDULED` -> `QUALIFIED` -> `PROPOSAL_SENT` -> `NEGOTIATION` -> `WON` -> `ARCHIVED`
- Transition to `LOST` is allowed from any stage except final ones.
- Transition to `ARCHIVED` is only permitted from `WON` or `LOST`.
- Invalid status updates trigger a `ValidationException` (HTTP 422).

### 5. Standardized Metadata Schemas
To ensure reliable consumption by future AI agents, activities validate strict JSON metadata models for `STATUS_CHANGED`, `ASSIGNED`, `TAG_ADDED`/`TAG_REMOVED`, and `NOTE_ADDED` events.

---

## Consequences

**Benefits:**
- Under concurrent loads (e.g., CSV imports, bulk API edits), lead sequences remain unique and collision-free.
- Sales executives cannot accidentally overwrite concurrent changes (lost updates prevented).
- Downstream AI parsing is fully reliable due to guaranteed JSON schemas on the timeline.
- Clean database level normalization (tags are pivot tables, not inline JSON lists).

**Trade-offs:**
- Requires clients to supply the current read `version` integer in all PATCH payloads.
- Status updates must go through progressive states (no jumping directly from NEW to WON unless transitioning to intermediate states sequentially).
