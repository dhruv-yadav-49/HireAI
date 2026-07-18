import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.dependencies import get_current_context
from app.core.context import RequestContext
from app.db.session import get_db
from app.models.enums import SuggestionStatus
from app.models.ai_prompt_suggestion import AIPromptSuggestion
from app.models.ai_policy_suggestion import AIPolicySuggestion
from app.schemas.learning import (
    DatasetListResponse,
    ImprovementListResponse,
    SuggestionActionRequest
)
from app.services.learning_service import LearningService

router = APIRouter(prefix="/learning", tags=["Learning"])


@router.post("/run", summary="Trigger continuous learning optimization run manually")
async def run_learning(
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    svc = LearningService(db)
    return await svc.run_manual_learning(ctx)


@router.get("/dataset", summary="List continuous learning dataset examples", response_model=DatasetListResponse)
async def list_dataset(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    svc = LearningService(db)
    return await svc.list_datasets(ctx, page, page_size)


@router.get("/improvements", summary="List pattern improvements detected", response_model=ImprovementListResponse)
async def list_improvements(
    status: Optional[SuggestionStatus] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    svc = LearningService(db)
    return await svc.list_improvements(ctx, status, page, page_size)


@router.get("/suggestions", summary="Fetch active prompt and policy Suggestions")
async def fetch_suggestions(
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    """Returns lists of prompt and policy suggestions for the organization."""
    prompts_stmt = select(AIPromptSuggestion).where(
        AIPromptSuggestion.organization_id == ctx.tenant_id
    )
    res_prompts = await db.execute(prompts_stmt)
    prompts = res_prompts.scalars().all()

    policies_stmt = select(AIPolicySuggestion).where(
        AIPolicySuggestion.organization_id == ctx.tenant_id
    )
    res_policies = await db.execute(policies_stmt)
    policies = res_policies.scalars().all()

    return {
        "prompt_suggestions": [
            {
                "id": str(p.id),
                "prompt_id": str(p.prompt_id) if p.prompt_id else None,
                "current_prompt": p.current_prompt,
                "suggested_prompt": p.suggested_prompt,
                "reason": p.reason,
                "pattern_confidence": p.pattern_confidence,
                "deployment_confidence": p.deployment_confidence,
                "status": p.status.value,
                "estimated_impact": p.estimated_impact,
                "affected_agents": p.affected_agents,
                "bundle_id": str(p.bundle_id) if p.bundle_id else None,
                "approval_id": str(p.approval_id) if p.approval_id else None,
                "created_at": p.created_at.isoformat()
            }
            for p in prompts
        ],
        "policy_suggestions": [
            {
                "id": str(pol.id),
                "policy_name": pol.policy_name,
                "current_rule": pol.current_rule,
                "suggested_rule": pol.suggested_rule,
                "reason": pol.reason,
                "status": pol.status.value,
                "bundle_id": str(pol.bundle_id) if pol.bundle_id else None,
                "approval_id": str(pol.approval_id) if pol.approval_id else None,
                "created_at": pol.created_at.isoformat()
            }
            for pol in policies
        ]
    }


@router.get("/analytics", summary="Get continuous learning health analytics metrics")
async def get_analytics(
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    svc = LearningService(db)
    return await svc.get_learning_analytics(ctx)


@router.post("/approve", summary="Approve prompt/policy suggestion")
async def approve_suggestion(
    body: SuggestionActionRequest,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    svc = LearningService(db)
    try:
        return await svc.approve_suggestion(ctx, body.suggestion_id, body.suggestion_type)
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))


@router.post("/reject", summary="Reject prompt/policy suggestion")
async def reject_suggestion(
    body: SuggestionActionRequest,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    svc = LearningService(db)
    try:
        return await svc.reject_suggestion(ctx, body.suggestion_id, body.suggestion_type)
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
