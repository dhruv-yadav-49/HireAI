# ADR-016: Multi-Agent Orchestrator

## Status
Approved

## Context
As the HireAI platform evolved from a single autonomous agent (Sales Executive) into a collaborative workforce (Business Analyst, Marketing Executive, etc.), we required an integration layer. Allowing agents to directly invoke each other creates tight coupling and limits runtime modularity (e.g. users enabling or disabling specific agent permissions dynamically).

## Decision
We decided to introduce a centralized **Agent Orchestrator** layer.

```
[Agent A] ──> [Orchestrator Layer] ──> [Agent B]
```

### Architectural Rules:
1. **Decoupled Invocation:** No agent directly calls another. Every interaction is routed through the orchestrator.
2. **Database-Backed Registry:** Agent metadata, capabilities, and configurations are stored in the database (`AIAgentDefinition`), enabling runtime configuration changes.
3. **State Machine Tracking:** Session task handoffs are managed via a robust state machine (`AIAgentTask` states: PENDING, DELEGATED, COMPLETED, FAILED, ROLLBACK).
4. **Versioned Context Handoffs:** Handoffs reference exact snapshot versions to maintain replication auditability.

## Consequences
- **Pros:** High flexibility, clean segregation of duties, easy agent runtime onboarding.
- **Cons:** Introduces extra database state writes during task transition segments.
