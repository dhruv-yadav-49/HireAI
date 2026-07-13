# ADR-007: Workflow Automation Foundation

**Status**: Accepted  
**Date**: 2026-07-13  
**Sprint**: 4A

---

## Context

We require a core Workflow Automation system to serve as the execution engine for downstream automation triggers (reminders, notification templates, scheduled workflows, and AI Sales agents). The system must be robust, isolated by tenant, and allow audit replayability of historic executions even if active workflow rules change.

## Decision

We have established these design principles for the Workflow Automation engine:

### 1. Snapshot and Definition Hash
- To ensure executions are reproducible and immune to subsequent rule edits, each execution caches the full configuration (workflow details, conditions, actions) as a `JSONB` document inside `workflow_snapshot`.
- We calculate the SHA-256 hash of this snapshot string (`workflow_definition_hash`) to quickly check rule modifications.

### 2. Condition Pre-Filters
- Workflows can define a `trigger_filter: JSONB` property (e.g. `{"status": ["NEW"]}`). This has no direct business meaning but acts as a quick index-level pre-filter before executing the full condition engine.

### 3. SKIPPED Execution State
- Condition false is not a failure. If conditions evaluate to False, the execution state is set to `SKIPPED`, and no actions run. This separates execution failures from simple condition mismatches.

### 4. Registry and Extension Patterns
- **Condition Operators**: Regulated by operator classes implementing an `Operator` protocol, mapped inside a central registry.
- **Action Handlers**: Mapped to dedicated service dispatcher classes implementing a common `ActionHandler` interface, decoupled from the workflow executor.
- **Action Validators**: Configurations are validated using Pydantic models registered under `CONFIG_VALIDATORS`.

### 5. Execution Step Independence Policy
- Actions execute sequentially ordered by `order ASC`.
- Each action step commits independently in the database. If Step 2 fails, Step 1 is NOT rolled back.

### 6. Synchronous Execution Model Justification
- **Sync Event Handlers**: For the initial Sprint 4A MVP, event subscribers intercept domain events and invoke the `WorkflowExecutor` synchronously in the same HTTP thread request.
- **Justification**: This avoids adding Celery, Redis Streams, or RabbitMQ background queues for the initial local deploy, keeping infrastructure light. The publisher-subscriber decoupling ensures we can swap execution to background queues in Sprints 6 without modifying core services or executor pipelines.

---

## Design Rationales & Justifications

### 1. Why Immutable Snapshot?
To ensure executions are completely reproducible and audit-safe, each execution captures the entire active state of the workflow and its relations (conditions, actions) in a `JSONB` document inside `workflow_snapshot`. If a workflow definition is modified or deleted in the future, past executions remain fully readable, replayable, and understandable.
Furthermore, to prevent key order differences from yielding different hashes, the snapshot is serialized using sorted keys (`sort_keys=True`) before generating the SHA-256 `workflow_definition_hash`.

### 2. Why No Transaction Rollbacks?
Because workflow action steps interact with external systems (e.g. sending SMS, WhatsApp alerts, Slack notifications, or dispatching emails), rolling back database transactions on subsequent failures is impossible. If Step 1 creates a database task and Step 2 sends an email but fails, rolling back Step 1 would lead to an inconsistent state (the email was sent, but the CRM task was rolled back). 
To align with real-world integrations, we use **Execution Step Independence**: preceding steps commit independently, and subsequent steps are marked as `SKIPPED` with a logged `skipped_reason`.

### 3. Caching Strategy for High Read Throughput
In subsequent sprints, checking active workflow rules on every database transaction event could bottleneck database read IOPS. We will introduce a Redis/in-memory cache wrapper around `WorkflowRepository` to query active triggers in $O(1)$ time, skipping database overhead entirely for events that do not trigger active rules.

---

## Consequences

- **Highly decoupled services**: Lead and task models publish standard domain events and remain unaware of the workflow system.
- **Observability and replayability**: Historically accurate snapshots, condition traces (with evaluation durations), execution modes, and truncation flags are logged.
- **Fail-safe isolation**: Exceptions inside the sync workflow execution loop are caught and logged inside the subscriber, keeping parent request operations safe.
- **Easy extensibility**: New triggers and action integrations (Email, WhatsApp) can be built using standard registry subclasses without rewriting executor pipelines.
