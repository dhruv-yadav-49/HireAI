# ADR-017: AI Observability & Evaluation

## Status
Approved

## Context
To support enterprise production SLA demands, users must understand *why* the AI generated a specific output, what tools it chose, and how well it performed. Crucially, the diagnostic layer must not interfere with core execution reliability.

## Decision
We implemented a passive, decoupled Observability and Evaluation subsystem matching OpenTelemetry standards.

### Architectural Rules:
1. **Passive Logging:** All trace writes (`TraceCollector`) are wrapped in try/except blocks. Under no circumstances should telemetry errors block core customer executions.
2. **OpenTelemetry Span Hierarchy:** Telemetry spans are structured in a parent-child relationship (Execution → Prompt / Retrieval / Tool spans) to ease exportation.
3. **9-Dimension Evaluators:** Automated quality scores evaluate runs against Grounding, Hallucination, Retrieval, Planning, Reasoning, Policy, Latency, Cost, and Tool success metrics.
4. **Actionable Overrides:** Organizations configure Quality Rules that define actions (`WARN`, `FAIL`, `BLOCK`, `NOTIFY`) when scores fall below thresholds.

## Consequences
- **Pros:** Full visibility into LLM executions, automated quality grading, standards compliance (OpenTelemetry exports).
- **Cons:** Elevated database row volume due to granular span storage. Mitigation: Expiration fields (`expires_at`) are set on executions for automatic archiving.
