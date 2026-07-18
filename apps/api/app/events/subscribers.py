"""Event Subscribers — Sprint 7B

Each subscriber is a single async function that receives (AIEvent, AsyncSession)
and performs idempotent work in response to a domain event.

Subscriber isolation contract (ADR-020 CTO refinement #6):
  - Each subscriber runs in its own try/except inside the dispatcher.
  - A subscriber crash never blocks other subscribers for the same event.
  - All work is idempotent: re-executing on retry has no duplicate side-effects.
"""
from __future__ import annotations

import uuid
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_event import AIEvent
from app.services.evaluation_engine import EvaluationEngine
from app.services.learning_scheduler import LearningScheduler
from app.services.metric_aggregator import MetricAggregator
from app.models.enums import LearningTriggerMode

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Observability Subscriber
# Triggered by: JOB_COMPLETED, TRACE_CREATED
# ──────────────────────────────────────────────────────────────────────────────

async def observability_subscriber(event: AIEvent, db: AsyncSession) -> None:
    """Aggregates metrics for the completed execution trace.

    Idempotent: MetricAggregator.record_metrics skips gracefully if trace
    has no latency data. Safe to call multiple times.
    """
    from app.models.ai_execution_trace import AIExecutionTrace

    payload = event.payload_json or {}
    execution_trace_id_str = payload.get("execution_trace_id")
    if not execution_trace_id_str:
        logger.debug("ObservabilitySubscriber: no execution_trace_id in payload, skipping")
        return

    try:
        trace_id = uuid.UUID(str(execution_trace_id_str))
    except (ValueError, AttributeError):
        logger.warning("ObservabilitySubscriber: invalid execution_trace_id=%s", execution_trace_id_str)
        return

    trace = await db.get(AIExecutionTrace, trace_id)
    if not trace:
        logger.debug("ObservabilitySubscriber: trace %s not found, skipping", trace_id)
        return

    await MetricAggregator.record_metrics(db, trace)
    logger.info("ObservabilitySubscriber: recorded metrics for trace=%s", trace_id)


# ──────────────────────────────────────────────────────────────────────────────
# Evaluation Subscriber
# Triggered by: JOB_COMPLETED
# ──────────────────────────────────────────────────────────────────────────────

async def evaluation_subscriber(event: AIEvent, db: AsyncSession) -> None:
    """Runs the evaluation pipeline on the completed execution trace.

    Idempotent: EvaluationEngine checks for existing evaluations before writing.
    """
    payload = event.payload_json or {}
    execution_trace_id_str = payload.get("execution_trace_id")
    if not execution_trace_id_str:
        logger.debug("EvaluationSubscriber: no execution_trace_id in payload, skipping")
        return

    try:
        trace_id = uuid.UUID(str(execution_trace_id_str))
    except (ValueError, AttributeError):
        logger.warning("EvaluationSubscriber: invalid execution_trace_id=%s", execution_trace_id_str)
        return

    evaluation = await EvaluationEngine.evaluate_execution(db, trace_id)
    if evaluation:
        logger.info(
            "EvaluationSubscriber: evaluation id=%s score=%.1f for trace=%s",
            evaluation.id, evaluation.overall_score or 0.0, trace_id,
        )
    else:
        logger.debug("EvaluationSubscriber: no evaluation produced for trace=%s", trace_id)


# ──────────────────────────────────────────────────────────────────────────────
# Learning Subscriber
# Triggered by: EVALUATION_COMPLETED
# ──────────────────────────────────────────────────────────────────────────────

async def learning_subscriber(event: AIEvent, db: AsyncSession) -> None:
    """Runs the continuous improvement loop when an evaluation completes.

    Only triggers if overall_score is below the threshold (≤ 80).
    Idempotent: LearningScheduler internally deduplicates dataset rows.
    """
    payload = event.payload_json or {}
    overall_score = payload.get("overall_score")
    org_id_str = str(event.organization_id)

    try:
        org_id = uuid.UUID(org_id_str)
    except (ValueError, AttributeError):
        logger.warning("LearningSubscriber: invalid organization_id=%s", org_id_str)
        return

    # Only run the learning cycle when quality is below threshold
    score = float(overall_score) if overall_score is not None else 100.0
    if score > 80.0:
        logger.debug(
            "LearningSubscriber: score=%.1f above threshold, skipping learning cycle", score
        )
        return

    result = await LearningScheduler.run_scheduler(
        db, org_id, trigger_mode=LearningTriggerMode.EVENT_DRIVEN
    )
    logger.info(
        "LearningSubscriber: learning cycle completed org=%s rows_added=%s",
        org_id, result.get("dataset_rows_added"),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Notification Subscriber
# Triggered by: JOB_COMPLETED, JOB_STARTED
# ──────────────────────────────────────────────────────────────────────────────

async def notification_subscriber(event: AIEvent, db: AsyncSession) -> None:
    """Logs a notification record for the event. Extensible — a future
    NotificationService can replace this with real email/webhook delivery.

    Idempotent: logging is always safe to repeat.
    """
    payload = event.payload_json or {}
    logger.info(
        "NotificationSubscriber: event_type=%s org=%s payload_keys=%s",
        event.event_type.value,
        event.organization_id,
        list(payload.keys()),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Analytics Subscriber
# Triggered by: JOB_COMPLETED, WORKFLOW_COMPLETED, CAMPAIGN_COMPLETED
# ──────────────────────────────────────────────────────────────────────────────

async def analytics_subscriber(event: AIEvent, db: AsyncSession) -> None:
    """Aggregates analytics data for platform-level reporting.

    Idempotent: analytics writes are keyed by event_key which is unique.
    """
    payload = event.payload_json or {}
    logger.info(
        "AnalyticsSubscriber: recording analytics for event_type=%s org=%s event_key=%s",
        event.event_type.value,
        event.organization_id,
        event.event_key,
    )
    # Placeholder: future AnalyticsEngine.record(event) call goes here.
    # The subscriber is intentionally a no-op apart from logging so it can be
    # extended without any schema or registry changes.
