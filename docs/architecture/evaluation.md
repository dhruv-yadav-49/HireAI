# AI Evaluation Framework Architecture Guide

This document details the automated post-execution evaluation scoring engines of the HireAI platform.

## Scoring Flow

Immediately after execution completes, the `EvaluationEngine` triggers 9 independent evaluators to compile objective quality scores:

```
AI Execution Completes
        │
        ▼
   Observability
        │
        ▼
Evaluation Engine
  ├── Grounding
  ├── Retrieval (Precision / Recall / Coverage)
  ├── Planning
  ├── Reasoning
  ├── Policy (Violations check)
  ├── Tools (Retries / Recovery success)
  ├── Latency (SLA limits check)
  ├── Cost
  └── Hallucination
        │
        ▼
Evaluation Aggregator --> Custom Weights (AIQualityProfile)
        │
        ▼
   Quality Grade (A/B/C/D/F)
```

## Evaluator Engines

### 1. Grounding & Hallucination
Evaluates response alignment against retrieved documents. If facts are introduced that do not exist in vector hits, grounding score drops. Hallucination risk is mapped separately.

### 2. Retrieval Accuracy
Scores precision, recall, and coverage rates across memory logging and knowledge bases.

### 3. Policy Violations
Checks for DENY or BLOCK triggers. A single policy block decays the final grade immediately to an `F` via custom quality rule overrides.

### 4. Weights Profiles (`AIQualityProfile`)
Organizations can configure custom metric weight matrices (e.g. prioritizing Latency or Grounding higher based on specific workflow constraints).
