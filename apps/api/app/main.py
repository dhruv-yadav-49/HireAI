import uuid
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import AppException
from app.api.v1.auth.router import router as auth_router
from app.api.v1.organizations.router import router as org_router
from app.api.v1.leads.router import router as leads_router
from app.api.v1.tasks.router import router as tasks_router
from app.api.v1.workflows.router import router as workflows_router
from app.api.v1.scheduler.router import router as scheduler_router
from app.api.v1.communications.router import router as communications_router
from app.api.v1.ai.router import router as ai_router
from app.api.v1.memory.router import router as memory_router
from app.api.v1.sales_ai.router import router as sales_ai_router
from app.api.v1.agents.router import router as agents_router
from app.api.v1.business_ai.router import router as business_ai_router
from app.api.v1.marketing_ai.router import router as marketing_ai_router
from app.api.v1.observability.router import router as observability_router
from app.api.v1.evaluation.router import router as evaluation_router
from app.api.v1.learning.router import router as learning_router
from app.api.v1.jobs.router import router as jobs_router
from app.api.v1.events.router import router as events_router
from app.api.v1.security.router import router as security_router
from app.api.v1.governance.router import router as governance_router
from app.api.v1.playground.router import router as playground_router

app = FastAPI(
    title=settings.APP_NAME,
    description="HireAI Production API — Multi-tenant SaaS backend",
    version="0.1.0",
)


scheduler_task = None


@app.on_event("startup")
async def startup_event():
    from app.core.events import LocalEventPublisher, set_event_publisher
    from app.services.workflow_subscriber import workflow_event_subscriber

    local_pub = LocalEventPublisher()
    local_pub.subscribe(workflow_event_subscriber)
    set_event_publisher(local_pub)

    # ── Sprint 7B: Seed Event Bus Subscriptions (idempotent) ─────────────────
    # Registers all platform subscribers in the database so that the
    # EventRouter can fan-out new events without manual DB intervention.
    await _seed_event_subscriptions()

    # Start background scheduler polling loop
    from app.services.scheduler_service import SchedulerService
    global scheduler_task
    scheduler_task = asyncio.create_task(SchedulerService.start_polling())


async def _seed_event_subscriptions() -> None:
    """Idempotent startup seeding of event subscriptions (CTO refinement #13).

    Uses EventRepository.upsert_subscription() which is safe to call
    multiple times across restarts without creating duplicate rows.
    """
    import logging
    from app.db.session import AsyncSessionFactory
    from app.models.enums import EventType
    from app.repositories.event_repository import EventRepository
    from app.events.event_registry import EventRegistry
    from app.events.subscribers import (
        observability_subscriber,
        evaluation_subscriber,
        learning_subscriber,
        notification_subscriber,
        analytics_subscriber,
    )

    logger = logging.getLogger(__name__)

    # Register handlers in the in-process EventRegistry
    EventRegistry.register(
        "observability_subscriber",
        observability_subscriber,
        timeout_seconds=30,
    )
    EventRegistry.register(
        "evaluation_subscriber",
        evaluation_subscriber,
        timeout_seconds=60,
    )
    EventRegistry.register(
        "learning_subscriber",
        learning_subscriber,
        timeout_seconds=120,
    )
    EventRegistry.register(
        "notification_subscriber",
        notification_subscriber,
        timeout_seconds=10,
    )
    EventRegistry.register(
        "analytics_subscriber",
        analytics_subscriber,
        timeout_seconds=10,
    )

    # Persist subscriptions to DB so EventRouter can look them up
    subscriptions_to_seed = [
        # JOB_COMPLETED fans out to 4 subscribers
        ("observability_subscriber", EventType.JOB_COMPLETED, 30, 3),
        ("evaluation_subscriber",    EventType.JOB_COMPLETED, 60, 3),
        ("notification_subscriber",  EventType.JOB_COMPLETED, 10, 2),
        ("analytics_subscriber",     EventType.JOB_COMPLETED, 10, 2),
        # EVALUATION_COMPLETED triggers the learning loop
        ("learning_subscriber",      EventType.EVALUATION_COMPLETED, 120, 3),
        # WORKFLOW_COMPLETED and CAMPAIGN_COMPLETED feed analytics
        ("analytics_subscriber",     EventType.WORKFLOW_COMPLETED, 10, 2),
        ("analytics_subscriber",     EventType.CAMPAIGN_COMPLETED, 10, 2),
    ]

    try:
        async with AsyncSessionFactory() as db:
            repo = EventRepository(db)
            for subscriber_name, event_type, timeout_s, retry_limit in subscriptions_to_seed:
                await repo.upsert_subscription(
                    subscriber_name=subscriber_name,
                    event_type=event_type,
                    timeout_seconds=timeout_s,
                    retry_limit=retry_limit,
                )
            await db.commit()
        logger.info("Event Bus: seeded %d subscriptions", len(subscriptions_to_seed))
    except Exception as exc:
        logger.warning("Event Bus: subscription seeding failed (non-fatal): %s", exc)


@app.on_event("shutdown")
async def shutdown_event():
    global scheduler_task
    if scheduler_task:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass


# ── X-Request-ID middleware ────────────────────────────────────────────────────
# Injects a unique request ID if the client doesn't provide one, and echoes
# it back in every response header. Useful for correlating frontend logs with
# backend traces. (ADR-003)

@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    """Sprint 7C middleware order (CTO refinement #11):
    RequestID → RateLimiter → Authentication → Authorization →
    PII Scan → Business Logic → Audit Logger → Response
    """
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    # ── Rate Limiter (in-process sliding window) ───────────────────────────────
    # Runs after RequestID is assigned so the key can include it.
    # Org-based limiting is enforced inside route handlers via SecurityService.
    # IP-based limiting guards unauthenticated endpoints here.
    try:
        from app.security.rate_limiter import get_rate_limiter
        ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or (request.client.host if request.client else "unknown")
        )
        limiter = get_rate_limiter()
        result = limiter.check_ip(ip)
        if not result.allowed:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={"Retry-After": str(int(result.retry_after_seconds or 60))},
            )
    except Exception:
        pass  # Rate limiter failure is non-fatal

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ── Global exception handler ───────────────────────────────────────────────────

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


# ── Routes ─────────────────────────────────────────────────────────────────────

app.include_router(auth_router, prefix="/api/v1")
app.include_router(org_router, prefix="/api/v1")
app.include_router(leads_router, prefix="/api/v1")
app.include_router(tasks_router, prefix="/api/v1")
app.include_router(workflows_router, prefix="/api/v1")
app.include_router(scheduler_router, prefix="/api/v1")
app.include_router(communications_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")
app.include_router(memory_router, prefix="/api/v1")
app.include_router(sales_ai_router, prefix="/api/v1")
app.include_router(agents_router, prefix="/api/v1")
app.include_router(business_ai_router, prefix="/api/v1")
app.include_router(marketing_ai_router, prefix="/api/v1")
app.include_router(observability_router, prefix="/api/v1")
app.include_router(evaluation_router, prefix="/api/v1")
app.include_router(learning_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(events_router, prefix="/api/v1")
app.include_router(security_router, prefix="/api/v1")
app.include_router(governance_router, prefix="/api/v1")
app.include_router(playground_router, prefix="/api/v1")


@app.get("/", tags=["health"])
def read_root():
    return {"status": "ok", "service": settings.APP_NAME}


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}
