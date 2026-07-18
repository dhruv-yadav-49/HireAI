# Continuous Learning & Human Feedback Architecture Guide

This document details the closed-loop optimization pipelines of the HireAI platform.

## Closed-Loop Cycle

HireAI utilizes post-execution quality grades and human comments to identify failures, discover patterns, and suggest configurations optimizations without automatically altering model weights:

```
Runtime Executions
        │
        ▼
Observability Traces (6A)
        │
        ▼
Evaluations (6B)
        │
        ▼
Human Feedback Collector
        │
        ▼
Append-only Dataset Examples
        │
        ▼
Learning Engine Optimizers (Prompt, Planner, Retrieval, Policy)
        │
        ▼
Suggestion Bundles (linked to AIApproval governance)
        │
        ▼
Human Review & Deployment
```

## Architectural Elements

### 1. `FeedbackCollector`
Ingests completed evaluation records and logs expected comments or rating stars, saving records as immutable training rows in the dataset.

### 2. Optimizers
- **PromptOptimizer**: Compiles suggestions for system prompt updates when repeated warnings appear.
- **PlannerOptimizer**: Targets planner failures, duplicate tool calls, or redundant steps, proposing workflow adjustments.
- **RetrievalOptimizer**: Proposes Top-K value shifts and CRM/Memory context boosting multipliers.
- **PolicyOptimizer**: Reports override statistics to recommend relaxing safety thresholds when positive reviews occur.

### 3. Suggestions Bundles & Approvals
Groups related optimizations under a `bundle_id` to allow a single review workflow to approve all changes. Every proposed suggestion is registered in the `AIApproval` database schema, enforcing governance checks.
