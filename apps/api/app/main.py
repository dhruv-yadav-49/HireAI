import uuid
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import AppException
from app.api.v1.auth.router import router as auth_router
from app.api.v1.organizations.router import router as org_router
from app.api.v1.leads.router import router as leads_router
from app.api.v1.tasks.router import router as tasks_router

app = FastAPI(
    title=settings.APP_NAME,
    description="HireAI Production API — Multi-tenant SaaS backend",
    version="0.1.0",
)


# ── X-Request-ID middleware ────────────────────────────────────────────────────
# Injects a unique request ID if the client doesn't provide one, and echoes
# it back in every response header. Useful for correlating frontend logs with
# backend traces. (ADR-003)

@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
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


@app.get("/", tags=["health"])
def read_root():
    return {"status": "ok", "service": settings.APP_NAME}


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}
