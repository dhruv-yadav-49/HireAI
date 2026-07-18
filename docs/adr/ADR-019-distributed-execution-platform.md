# ADR-019: Distributed Execution Platform

## Status
Approved

## Context
As the volume and complexity of AI agent runs grew, executing tasks synchronously inside request/response threads became a bottleneck. Long-running Sales, Marketing, and BI tasks blocked API gateway processes, risked timeout terminations, lacked automatic retry logic, and made cooperative execution cancellation impossible.

## Decision
We implemented a Redis-backed priority job queue wrapper around the core AI Runtime, enabling decoupled worker node processing.

```
                  [FastAPI Gateway]
                          │
                  Submit job request
                          │
                          ▼
                  [QueueRepository]
                          │
                          ▼
                    [Redis Queue]
                          │
          Visibility Timeout & Lease Renewal
                          │
             ┌────────────┼────────────┐
             ▼            ▼            ▼
         [Worker A]   [Worker B]   [Worker C]
             │            │            │
             └────────────┬────────────┘
                          ▼
                [Cooperative Executor]
                          │
                          ▼
                    [AI Runtime]
```

### Architectural Principles:
1. **Asynchronous by Default:** Long-running AI workloads run out-of-process in worker threads.
2. **Runtime Reuse:** The distributed execution wraps the existing `AIRuntime` without changing core business logic.
3. **Lease-Based Job Ownership:** Workers claim jobs with a 5-minute database lease. Stuck or crashed jobs are automatically released and re-queued when the lease expires.
4. **Visibility Timeout:** Dequeued items remain invisible to other workers for 60 seconds. If not acknowledged (ACK), they return to the queue.
5. **Idempotent Execution:** Duplicate requests (matching same `idempotency_key` and payload hash) return existing job records instead of spawning duplicates.
6. **Cooperative Cancellation:** Workers check job status at boundary checkpoints (Prompt compile, RAG retrieval, Planning, Policy check, and Tool execution) to halt cancelled runs cleanly without force-killing threads.
7. **Backpressure Protections:** Configuring queue size thresholds to throttle (sleep/delay) or reject new jobs when queue depths grow too large.
8. **Queue Isolation:** Distinct partitions (Default, Priority, Long Running, Sales, Marketing, Analytics) permit selective worker subscriptions.

## Consequences
- **Pros:** Horizontally scalable workers, resilience against crashes, cooperative cancellations, and zero overhead on API request latencies.
- **Cons:** Elevated database telemetry logs during job lifecycle events.
