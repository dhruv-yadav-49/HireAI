# ADR-018: Continuous Learning & Human Feedback

## Status
Approved

## Context
AI performance degrades over time. Correcting errors requires collecting failure examples and optimizing configuration assets. Automatically retraining or fine-tuning weights introduces significant safety risks and high financial costs.

## Decision
We implemented a closed-loop configuration optimizer framework that improves prompts, planners, retrieval, and policies based on traces and ratings, governed by manual human reviews.

### Architectural Rules:
1. **Human-in-the-Loop:** Suggestions are never applied to production automatically. Suggestions must be approved via the standard `AIApproval` governance loop.
2. **Immutable Learning Dataset:** Compiled learning training instances (`AILearningDataset`) are append-only.
3. **Optimizers Segregation:** Specialized optimizers analyze isolated parts of the trace (Prompt, Planner, Retrieval, Policy) independently.
4. **Traceable Explanations:** Suggestions explain the rationale for changes, affected agents, and deployment/pattern confidence levels.

## Consequences
- **Pros:** Safe continuous improvement, clear audit records, zero downtime/fine-tuning costs.
- **Cons:** Prompts/Planners need versioned schemas to allow selective deployment of approved suggestion assets.
