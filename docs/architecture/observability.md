# AI Observability Architecture Guide

This document details the telemetry, spans collection, and timeline visualizer layer of the HireAI platform.

## Tracing Concept

HireAI maps executions to an OpenTelemetry-compatible parent-child span tree structure, providing full trace accountability from user queries to individual tool invocations.

```
Execution Trace (Root Span)
├── Prompt Trace (Child Span)
├── Retrieval Trace (Child Span)
│   ├── Memory retrieval
│   ├── CRM retrieval
│   └── Knowledge retrieval
├── Planning Trace (Child Span)
├── Policy Trace (Child Span)
└── Tool Traces (Child Spans per Tool)
```

## Architectural Elements

### 1. `TraceCollector`
A non-blocking write-point service. All collector database queries are wrapped in try/except blocks to guarantee trace recording errors never abort core business execution flow.

### 2. Spans Database Models
- `AIExecutionTrace`: Stores top-level organization context, correlation IDs, status, overall latency, and final error stack-traces.
- `AIPromptTrace`: Saves compiled prompts, hashes, and token breakdown metrics.
- `AIRetrievalTrace`: Stores query keywords and granular per-source latency statistics (CRM vs Memory vs vector searches).
- `AIToolTrace`: Logs tool arguments, outputs, retries count, and duration.
- `AIMetric`: High-speed flat metric rows populated post-execution for swift analytics query aggregates.

### 3. `ExecutionVisualizer`
Reconstructs execution timeline data by ordering trace records chronologically using `step_index` properties.

### 4. `TraceExporter`
Translates execution database models into JSON, CSV, or OpenTelemetry (OTel ScopeSpans) formats.
