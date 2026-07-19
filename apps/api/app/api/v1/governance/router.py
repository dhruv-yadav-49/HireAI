"""
app/api/v1/governance/router.py

Enterprise AI Governance REST API — 12 endpoints.

All endpoints require authentication via RequestContext & SecurityContext.
Admin/Owner roles required for policy management and compliance report generation.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, get_request_context
from app.core.context import RequestContext
from app.governance.governance_context import build_governance_context
from app.governance.policy_pack_registry import get_policy_pack_registry
from app.governance.risk_engine import get_risk_engine
from app.models.enums import ComplianceFramework, PolicyPackType
from app.repositories.governance_repository import GovernanceRepository
from app.security.security_service_helper import build_security_ctx_from_request_ctx
from app.services.governance_service import GovernanceService

router = APIRouter(prefix="/governance", tags=["AI Governance"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class EvaluateActionRequest(BaseModel):
    action_type: str
    action_payload: Optional[Dict[str, Any]] = None
    job_type: Optional[str] = None
    agent_type: Optional[str] = None
    resource_type: Optional[str] = None


class EvaluateActionResponse(BaseModel):
    decision_id: str
    decision_status: str
    risk_score: float
    risk_level: str
    reason: str
    explanation_json: Dict[str, Any]
    policy_name: str
    cached: bool


class ApprovalActionRequest(BaseModel):
    comment: Optional[str] = None


class GovernancePolicyUpdateRequest(BaseModel):
    pack_type: str = "DEFAULT"
    rules: Dict[str, Any]


class RiskSimulationRequest(BaseModel):
    action_type: str
    action_payload: Optional[Dict[str, Any]] = None


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/evaluate", response_model=EvaluateActionResponse)
async def evaluate_action(
    body: EvaluateActionRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """Evaluate an AI action through the Governance Engine."""
    sec_ctx = build_security_ctx_from_request_ctx(ctx)
    gov_ctx = build_governance_context(
        security_context=sec_ctx,
        action_type=body.action_type,
        action_payload=body.action_payload,
        job_type=body.job_type,
        agent_type=body.agent_type,
        resource_type=body.resource_type,
    )

    service = GovernanceService(db)
    record, result = await service.evaluate_and_persist(gov_ctx)
    await db.commit()

    return EvaluateActionResponse(
        decision_id=str(record.id),
        decision_status=result.decision_status.value,
        risk_score=result.risk_score,
        risk_level=result.risk_level.value,
        reason=result.reason,
        explanation_json=result.explanation_json,
        policy_name=result.policy_name,
        cached=result.cached,
    )


@router.get("/decisions")
async def list_decisions(
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """Paginated decision audit log for organization."""
    repo = GovernanceRepository(db)
    decisions = await repo.list_decisions(ctx.tenant_id, limit=limit, offset=offset)
    return [
        {
            "id": str(d.id),
            "action_type": d.action_type,
            "risk_score": d.risk_score,
            "risk_level": d.risk_level.value,
            "decision_status": d.decision_status.value,
            "policy_name": d.policy_name,
            "decided_at": d.decided_at.isoformat(),
        }
        for d in decisions
    ]


@router.get("/approvals")
async def list_pending_approvals(
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """List pending human approval requests for the organization."""
    repo = GovernanceRepository(db)
    approvals = await repo.list_pending_approvals(ctx.tenant_id)
    return [
        {
            "id": str(a.id),
            "decision_id": str(a.governance_decision_id),
            "status": a.status.value,
            "reason": a.reason,
            "leased_by": str(a.leased_by) if a.leased_by else None,
            "expires_at": a.expires_at.isoformat(),
            "created_at": a.created_at.isoformat(),
        }
        for a in approvals
    ]


@router.post("/approvals/{approval_id}/approve")
async def approve_request(
    approval_id: uuid.UUID,
    body: ApprovalActionRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """Approve an escalated AI action."""
    if not ctx.is_admin():
        raise HTTPException(403, "Only admins can approve escalated actions.")

    service = GovernanceService(db)
    approval = await service.approve_action(approval_id, ctx.user.id, body.comment)
    await db.commit()
    return {"id": str(approval.id), "status": approval.status.value}


@router.post("/approvals/{approval_id}/reject")
async def reject_request(
    approval_id: uuid.UUID,
    body: ApprovalActionRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """Reject an escalated AI action."""
    if not ctx.is_admin():
        raise HTTPException(403, "Only admins can reject escalated actions.")

    service = GovernanceService(db)
    approval = await service.reject_action(approval_id, ctx.user.id, body.comment)
    await db.commit()
    return {"id": str(approval.id), "status": approval.status.value}


@router.get("/policies")
async def get_governance_policy(
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """Get active organization governance policy."""
    repo = GovernanceRepository(db)
    policy = await repo.get_policy(ctx.tenant_id)
    if not policy:
        registry = get_policy_pack_registry()
        default_pack = registry.get_pack(PolicyPackType.DEFAULT)
        return {
            "version": 1,
            "pack_type": default_pack.pack_type.value,
            "rules": default_pack.rules,
            "is_default": True,
        }
    return {
        "id": str(policy.id),
        "version": policy.version,
        "pack_type": policy.pack_type.value,
        "rules": policy.rules_json,
        "published_at": policy.published_at.isoformat() if policy.published_at else None,
    }


@router.put("/policies")
async def update_governance_policy(
    body: GovernancePolicyUpdateRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """Create a new versioned governance policy for organization."""
    if not ctx.is_owner():
        raise HTTPException(403, "Only organization owners can update governance policies.")

    repo = GovernanceRepository(db)
    existing = await repo.get_policy(ctx.tenant_id)
    next_version = (existing.version + 1) if existing else 1

    try:
        pack_type = PolicyPackType(body.pack_type)
    except ValueError:
        pack_type = PolicyPackType.CUSTOM

    new_policy = await repo.create_policy_version(
        org_id=ctx.tenant_id,
        pack_type=pack_type,
        rules=body.rules,
        version=next_version,
    )
    await db.commit()
    return {"id": str(new_policy.id), "version": new_policy.version, "pack_type": new_policy.pack_type.value}


@router.get("/compliance")
async def list_compliance_reports(
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """List generated compliance report snapshots."""
    repo = GovernanceRepository(db)
    reports = await repo.list_compliance_reports(ctx.tenant_id)
    return [
        {
            "id": str(r.id),
            "framework": r.framework.value,
            "score": r.score,
            "total_decisions": r.total_decisions,
            "generated_at": r.generated_at.isoformat(),
        }
        for r in reports
    ]


@router.post("/compliance/generate")
async def generate_compliance_report(
    framework: str = Query("SOC2"),
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """Generate an on-demand compliance report snapshot."""
    if not ctx.is_admin():
        raise HTTPException(403, "Only admins can generate compliance reports.")

    try:
        fw_enum = ComplianceFramework(framework)
    except ValueError:
        fw_enum = ComplianceFramework.SOC2

    service = GovernanceService(db)
    report = await service.generate_compliance_snapshot(ctx.tenant_id, fw_enum)
    await db.commit()

    return {
        "id": str(report.id),
        "framework": report.framework.value,
        "score": report.score,
        "controls": report.controls_json,
    }


@router.get("/metrics")
async def get_governance_metrics(
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """Get aggregated governance performance metrics."""
    service = GovernanceService(db)
    summary = await service.get_metrics_summary(ctx.tenant_id)
    return summary.__dict__


@router.post("/risk/simulate")
async def simulate_risk(
    body: RiskSimulationRequest,
    ctx: RequestContext = Depends(get_request_context),
):
    """Dry-run risk simulation for an action without persisting records."""
    sec_ctx = build_security_ctx_from_request_ctx(ctx)
    gov_ctx = build_governance_context(
        security_context=sec_ctx,
        action_type=body.action_type,
        action_payload=body.action_payload,
    )
    risk_engine = get_risk_engine()
    res = risk_engine.calculate_risk(gov_ctx)
    return res.to_explanation_dict()
