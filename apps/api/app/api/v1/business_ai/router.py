import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.context import RequestContext
from app.api.dependencies import get_current_context
from app.schemas.business_ai import (
    AIAnalysisRequest,
    AIAnalysisResponse,
    AIReportRequest,
    AIBusinessReportResponse,
    AIForecastRequest,
    AIForecastResponse,
    AIRecommendationResponse
)
from app.services.business_ai_service import BusinessAIService

router = APIRouter(prefix="/business-ai", tags=["AI Business Intelligence Analyst"])


@router.post("/analyze")
async def run_analysis(
    body: Optional[AIAnalysisRequest] = None,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    service = BusinessAIService(db)
    try:
        res = await service.run_analysis(ctx)
        await db.commit()
        
        # Format list outputs to schemas
        return {
            "health_score": res["health_result"]["score"],
            "health_dimensions": res["health_result"]["dimensions"],
            "health_issues": res["health_result"]["issues"],
            "snapshot": res["snapshot"],
            "trends": res["trends"],
            "anomalies": res["anomalies"],
            "recommendations": res["recommendations"]
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/report", response_model=AIBusinessReportResponse)
async def generate_report(
    body: AIReportRequest,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    service = BusinessAIService(db)
    try:
        report = await service.generate_report(
            ctx,
            report_type=body.report_type,
            title=body.title,
            parent_report_id=body.parent_report_id
        )
        await db.commit()
        return report
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/forecast", response_model=AIForecastResponse)
async def run_forecast(
    body: AIForecastRequest,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    service = BusinessAIService(db)
    try:
        # Run analysis to fetch snapshot, then forecast
        analysis = await service.run_analysis(ctx, forecast_period=body.forecast_period)
        await db.commit()
        return analysis["forecast"]
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/recommendations/{rec_id}/delegate")
async def delegate_recommendation(
    rec_id: uuid.UUID,
    session_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    service = BusinessAIService(db)
    try:
        res = await service.delegate_recommendation(ctx, rec_id, session_id=session_id)
        await db.commit()
        
        # Serialize task output
        from app.schemas.orchestration import AIAgentTaskResponse
        return {
            "task": AIAgentTaskResponse.model_validate(res["task"]),
            "session_id": res["session_id"],
            "delegation_metrics": res["delegation_metrics"]
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/recommendations")
async def list_recommendations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    service = BusinessAIService(db)
    items, total = await service.repo.list_recommendations(ctx, page=page, page_size=page_size)
    return {
        "items": [AIRecommendationResponse.model_validate(r) for r in items],
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.get("/kpis")
async def list_kpi_snapshots(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    service = BusinessAIService(db)
    items, total = await service.repo.list_kpi_snapshots(ctx, page=page, page_size=page_size)
    return {
        "items": [items],
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.get("/reports")
async def list_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    service = BusinessAIService(db)
    items, total = await service.repo.list_reports(ctx, page=page, page_size=page_size)
    return {
        "items": [AIBusinessReportResponse.model_validate(r) for r in items],
        "total": total,
        "page": page,
        "page_size": page_size
    }
