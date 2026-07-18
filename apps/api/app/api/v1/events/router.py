"""Events REST API — Sprint 7B

Provides endpoints for:
  - Event bus health metrics
  - Subscription management
  - Event listing (per org)
  - Dead-letter queue inspection
  - Replay support
"""
from __future__ import annotations

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_context
from app.core.context import RequestContext
from app.db.session import get_db
from app.models.enums import EventType
from app.repositories.event_repository import EventRepository
from app.services.event_metrics_service import EventMetricsService

router = APIRouter(prefix="/events", tags=["Event Bus"])


# ── Health & Metrics ──────────────────────────────────────────────────────────

@router.get("/metrics")
async def get_event_bus_metrics(
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """Returns operational health metrics for the event bus."""
    svc = EventMetricsService(db)
    return await svc.summary()


@router.get("/metrics/subscribers")
async def get_subscriber_metrics(
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """Returns per-subscriber delivery success/failure breakdown."""
    svc = EventMetricsService(db)
    return await svc.subscriber_summary()


# ── Subscriptions ─────────────────────────────────────────────────────────────

@router.get("/subscriptions")
async def list_subscriptions(
    event_type: Optional[EventType] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """Lists all registered event subscriptions, optionally filtered by event type."""
    repo = EventRepository(db)
    subs = await repo.list_subscriptions(event_type=event_type)
    return [
        {
            "id": str(s.id),
            "subscriber_name": s.subscriber_name,
            "event_type": s.event_type.value,
            "subscriber_version": s.subscriber_version,
            "handler_version": s.handler_version,
            "enabled": s.enabled,
            "retry_limit": s.retry_limit,
            "timeout_seconds": s.timeout_seconds,
            "created_at": s.created_at.isoformat(),
        }
        for s in subs
    ]


# ── Events ───────────────────────────────────────────────────────────────────

@router.get("")
async def list_events(
    event_type: Optional[EventType] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """Lists events for the current organization."""
    repo = EventRepository(db)
    events = await repo.list_events(
        org_id=ctx.tenant_id,
        event_type=event_type,
        limit=limit,
    )
    return [
        {
            "id": str(e.id),
            "event_key": str(e.event_key),
            "event_type": e.event_type.value,
            "event_version": e.event_version,
            "schema_version": e.schema_version,
            "sequence_number": e.sequence_number,
            "aggregate_type": e.aggregate_type,
            "aggregate_id": str(e.aggregate_id) if e.aggregate_id else None,
            "status": e.status.value,
            "published_at": e.published_at.isoformat(),
        }
        for e in events
    ]


@router.get("/replay")
async def replay_events(
    event_type: EventType = Query(...),
    from_sequence: int = Query(default=1, ge=1),
    to_sequence: Optional[int] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """Returns events in sequence order for replay (CTO refinement #9)."""
    repo = EventRepository(db)
    events = await repo.list_replay_events(
        org_id=ctx.tenant_id,
        event_type=event_type,
        from_sequence=from_sequence,
        to_sequence=to_sequence,
        limit=limit,
    )
    return {
        "event_type": event_type.value,
        "from_sequence": from_sequence,
        "to_sequence": to_sequence,
        "count": len(events),
        "events": [
            {
                "id": str(e.id),
                "event_key": str(e.event_key),
                "sequence_number": e.sequence_number,
                "payload": e.payload_json,
                "published_at": e.published_at.isoformat(),
            }
            for e in events
        ],
    }


# ── Dead-Letter Queue ─────────────────────────────────────────────────────────

@router.get("/dead-letter")
async def list_dead_letter(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """Returns deliveries in DEAD_LETTER status for operational inspection."""
    repo = EventRepository(db)
    deliveries = await repo.list_dead_letter(limit=limit)
    return [
        {
            "id": str(d.id),
            "event_id": str(d.event_id),
            "subscriber_id": str(d.subscriber_id),
            "attempt": d.attempt,
            "dead_letter_reason": d.dead_letter_reason,
            "failed_subscriber": d.failed_subscriber,
            "failed_attempt": d.failed_attempt,
            "failed_at": d.failed_at.isoformat() if d.failed_at else None,
            "last_error": d.last_error,
        }
        for d in deliveries
    ]


@router.post("/admin/requeue-stale")
async def requeue_stale_leases(
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """Resets expired lease locks so stale deliveries can be reprocessed
    (admin operation — CTO refinement #2)."""
    repo = EventRepository(db)
    requeued = await repo.requeue_stale_leases()
    await db.commit()
    return {"requeued_count": requeued}
