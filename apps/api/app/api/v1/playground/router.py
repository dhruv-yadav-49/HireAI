"""
app/api/v1/playground/router.py

Enterprise AI Playground REST API — 8 endpoints.

All endpoints require authentication via RequestContext & SecurityContext.
Runs executions in Sandbox mode without production side-effects.
"""
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, get_request_context
from app.core.context import RequestContext
from app.models.enums import AIProvider, ComparisonType, PolicyPackType, SandboxIsolationLevel
from app.playground.evaluation_viewer import EvaluationViewer
from app.playground.governance_simulator import GovernanceSimulator
from app.playground.playground_context import build_playground_context
from app.playground.trace_viewer import TraceViewer
from app.security.security_service_helper import build_security_ctx_from_request_ctx
from app.services.playground_service import PlaygroundService

router = APIRouter(prefix="/playground", tags=["AI Playground"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    name: str = "Developer Playground Session"
    isolation_level: str = "READ_ONLY"


class RunPromptRequest(BaseModel):
    session_id: uuid.UUID
    prompt: str
    variables: Optional[Dict[str, Any]] = None
    provider: str = "MOCK"
    model_name: str = "mock-llm-v1"
    temperature: float = 0.7
    max_tokens: int = 1000


class ReplayTraceRequest(BaseModel):
    session_id: uuid.UUID
    trace_id: uuid.UUID
    prompt_override: Optional[str] = None
    model_override: Optional[str] = None
    temperature_override: Optional[float] = None


class CompareRequest(BaseModel):
    session_id: uuid.UUID
    comparison_type: str = "PROMPT"  # PROMPT, MODEL, GOVERNANCE
    prompt_a: Optional[str] = None
    prompt_b: Optional[str] = None
    models: Optional[List[str]] = None
    action_type: Optional[str] = None
    action_payload: Optional[Dict[str, Any]] = None
    variables: Optional[Dict[str, Any]] = None


class SimulateGovernanceRequest(BaseModel):
    action_type: str
    action_payload: Optional[Dict[str, Any]] = None
    policy_pack_type: str = "DEFAULT"


class EndSessionRequest(BaseModel):
    session_id: uuid.UUID


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/session")
async def start_session(
    body: CreateSessionRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """Start an isolated developer playground session."""
    sec_ctx = build_security_ctx_from_request_ctx(ctx)
    try:
        iso_enum = SandboxIsolationLevel(body.isolation_level)
    except ValueError:
        iso_enum = SandboxIsolationLevel.READ_ONLY

    service = PlaygroundService(db)
    session = await service.start_session(sec_ctx, name=body.name, isolation_level=iso_enum)
    await db.commit()

    return {
        "session_id": str(session.id),
        "name": session.name,
        "status": session.status.value,
        "isolation_level": session.isolation_level.value,
        "expires_at": session.expires_at.isoformat(),
    }


@router.post("/run")
async def run_prompt(
    body: RunPromptRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """Execute a prompt in the Sandbox environment without side-effects."""
    sec_ctx = build_security_ctx_from_request_ctx(ctx)
    try:
        provider_enum = AIProvider(body.provider.upper())
    except ValueError:
        provider_enum = AIProvider.MOCK

    service = PlaygroundService(db)
    res = await service.run_prompt_experiment(
        sec_ctx=sec_ctx,
        session_id=body.session_id,
        template=body.prompt,
        variables=body.variables,
        provider=provider_enum,
        model_name=body.model_name,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
    )
    await db.commit()
    return res


@router.post("/replay")
async def replay_trace(
    body: ReplayTraceRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """Replay a historical execution trace with parameter overrides in Sandbox mode."""
    sec_ctx = build_security_ctx_from_request_ctx(ctx)
    service = PlaygroundService(db)
    res = await service.replay_trace(
        sec_ctx=sec_ctx,
        session_id=body.session_id,
        trace_id=body.trace_id,
        prompt_override=body.prompt_override,
        model_override=body.model_override,
        temperature_override=body.temperature_override,
    )
    return res


@router.post("/compare")
async def compare_matrix(
    body: CompareRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """Run side-by-side prompt, model, or governance matrix comparisons."""
    sec_ctx = build_security_ctx_from_request_ctx(ctx)
    try:
        comp_enum = ComparisonType(body.comparison_type.upper())
    except ValueError:
        comp_enum = ComparisonType.PROMPT

    service = PlaygroundService(db)
    res = await service.run_comparison(
        sec_ctx=sec_ctx,
        session_id=body.session_id,
        comparison_type=comp_enum,
        prompt_a=body.prompt_a,
        prompt_b=body.prompt_b,
        models=body.models,
        action_type=body.action_type,
        action_payload=body.action_payload,
        variables=body.variables,
    )
    return res


@router.get("/traces/{trace_id}")
async def view_trace(
    trace_id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """View detailed execution tree for a trace in Playground (reuses Sprint 6A visualizer)."""
    return await TraceViewer.get_execution_trace(db, trace_id)


@router.get("/evaluation/{trace_id}")
async def view_evaluation(
    trace_id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """View evaluation score breakdown for a trace (reuses Sprint 6B evaluator)."""
    return await EvaluationViewer.get_evaluation_summary(db, trace_id)


@router.post("/governance/simulate")
async def simulate_governance(
    body: SimulateGovernanceRequest,
    ctx: RequestContext = Depends(get_request_context),
):
    """Simulate risk score and decision under a policy pack in dry-run mode."""
    sec_ctx = build_security_ctx_from_request_ctx(ctx)
    play_ctx = build_playground_context(security_context=sec_ctx)

    try:
        pack_enum = PolicyPackType(body.policy_pack_type.upper())
    except ValueError:
        pack_enum = PolicyPackType.DEFAULT

    simulator = GovernanceSimulator(play_ctx)
    return simulator.simulate_action(
        action_type=body.action_type,
        action_payload=body.action_payload,
        policy_pack_type=pack_enum,
    )


@router.post("/end")
async def end_session(
    body: EndSessionRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """Terminate and archive a playground session."""
    sec_ctx = build_security_ctx_from_request_ctx(ctx)
    service = PlaygroundService(db)
    await service.end_session(sec_ctx, body.session_id)
    await db.commit()
    return {"session_id": str(body.session_id), "status": "EXPIRED"}
