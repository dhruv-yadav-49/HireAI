import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.context import RequestContext
from app.api.dependencies import get_current_context
from app.schemas.marketing_ai import (
    AICampaignCreateRequest,
    AICampaignResponse,
    AIAudienceSegmentRequest,
    AIAudienceSegmentResponse,
    AIMarketingContentRequest,
    AIMarketingContentResponse,
    AIABTestRequest,
    AIABTestResponse,
    AICampaignExecutionRequest,
    AICampaignExecutionResponse
)
from app.services.marketing_ai_service import MarketingAIService
from app.services.campaign_performance_engine import CampaignAnalyticsEngine

router = APIRouter(prefix="/marketing-ai", tags=["AI Marketing Executive"])


@router.post("/campaigns", response_model=AICampaignResponse)
async def create_campaign(
    body: AICampaignCreateRequest,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    service = MarketingAIService(db)
    try:
        campaign = await service.create_campaign(
            ctx,
            name=body.name,
            campaign_type=body.campaign_type,
            campaign_goal=body.campaign_goal,
            priority=body.priority,
            strategy_json=body.strategy_json,
            parent_campaign_id=body.parent_campaign_id
        )
        await db.commit()
        return campaign
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/segment", response_model=AIAudienceSegmentResponse)
async def create_segment(
    body: AIAudienceSegmentRequest,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    service = MarketingAIService(db)
    try:
        segment = await service.create_segment(
            ctx,
            name=body.name,
            segment_type=body.segment_type,
            criteria_json=body.criteria_json
        )
        await db.commit()
        return segment
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/content", response_model=AIMarketingContentResponse)
async def generate_content(
    body: AIMarketingContentRequest,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    service = MarketingAIService(db)
    try:
        content = await service.generate_content(
            ctx,
            campaign_id=body.campaign_id,
            content_type=body.content_type,
            subject=body.subject,
            body_override=body.body,
            parent_content_id=body.parent_content_id,
            generation_prompt=body.generation_prompt
        )
        await db.commit()
        return content
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ab-test", response_model=AIABTestResponse)
async def setup_ab_test(
    body: AIABTestRequest,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    service = MarketingAIService(db)
    try:
        # Convert variants dict payload list
        variants_list = body.variants_json.get("variants", [])
        test = await service.setup_ab_test(ctx, body.campaign_id, variants_list)
        await db.commit()
        return test
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/campaigns/{campaign_id}/execute", response_model=AICampaignExecutionResponse)
async def execute_campaign(
    campaign_id: uuid.UUID,
    body: AICampaignExecutionRequest,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    service = MarketingAIService(db)
    try:
        if not body.segment_id:
            raise HTTPException(status_code=400, detail="segment_id is required for execution.")
        exec_rec = await service.execute_campaign(
            ctx,
            campaign_id=campaign_id,
            segment_id=body.segment_id,
            attribution_model=body.attribution_model
        )
        await db.commit()
        return exec_rec
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/analyze")
async def analyze_performance(
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    service = MarketingAIService(db)
    try:
        # Load all campaigns and executions to run overall ROI aggregation
        campaigns, _ = await service.repo.list_campaigns(ctx, page=1, page_size=100)
        
        campaigns_stats = []
        for camp in campaigns:
            execs, _ = await service.repo.list_executions(ctx, camp.id, page=1, page_size=1)
            if execs:
                campaigns_stats.append({
                    "name": camp.name,
                    "statistics": execs[0].statistics_json
                })

        analytics = CampaignAnalyticsEngine.analyze_campaigns(campaigns_stats)
        return analytics
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/campaigns")
async def list_campaigns(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    service = MarketingAIService(db)
    items, total = await service.repo.list_campaigns(ctx, page=page, page_size=page_size)
    return {
        "items": [AICampaignResponse.model_validate(c) for c in items],
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.get("/reports")
async def list_execution_reports(
    campaign_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    service = MarketingAIService(db)
    items, total = await service.repo.list_executions(ctx, campaign_id=campaign_id, page=page, page_size=page_size)
    return {
        "items": [AICampaignExecutionResponse.model_validate(e) for e in items],
        "total": total,
        "page": page,
        "page_size": page_size
    }
