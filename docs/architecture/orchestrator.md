# Multi-Agent Orchestration Architecture Guide

This document details the multi-agent orchestration layer that permits collaborative workforce pipelines.

## Orchestration Concept

To prevent tight coupling, HireAI enforces the principle: **One agent should never directly invoke another agent.** Every handoff or delegation task goes through the orchestration layer:

```
                     Agent Orchestrator
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
    Sales Executive                   Business Analyst
            │                                 │
            └────────────────┬────────────────┘
                             ▼
                    Marketing Executive
```

## Core Modules

### 1. Database Agent Registry (`AIAgentDefinition`)
Allows runtime registry configuration per organization tenant context, dynamically enabling/disabling agents without code changes.

### 2. Versioned Handoffs
Every task handoff is versioned with specific dataset checksums. If context parameters are modified, subsequent actions are tracked against that exact snapshot for replication sanity.

### 3. Handoff Flow State Machine
Manages delegation lifecycles across status enums:
- `PENDING`
- `DELEGATED`
- `RUNNING`
- `COMPLETED`
- `FAILED`
- `CANCELLED`
- `OVERRIDDEN`
- `ROLLBACK`

## Multi-Agent Scheduler
Orchestrates nightly batch reports or automated nurturing campaigns by triggering task queues.
