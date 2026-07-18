import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_context
from app.core.context import RequestContext
from app.db.session import get_db
from app.models.enums import EvaluationStatus, QualityGrade
from app.schemas.evaluation import (
    EvaluationRunRequest,
    EvaluationSummaryResponse,
    EvaluationListResponse,
    EvaluationDetailResponse,
    FeedbackCreateRequest,
    FeedbackResponse
)
from app.services.evaluation_service import EvaluationService

router = APIRouter(prefix="/evaluation", tags=["Evaluation"])


@router.post("/run", summary="Trigger evaluation of an execution trace", response_model=EvaluationSummaryResponse)
async def run_evaluation(
    body: EvaluationRunRequest,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    svc = EvaluationService(db)
    try:
        eval_record = await svc.trigger_evaluation(ctx, body.execution_trace_id)
        if not eval_record:
            raise HTTPException(status_code=404, detail="Execution trace not found.")
        return eval_record
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))


@router.post("/batch", summary="Batch evaluate execution traces (Reserved Architecture)", status_code=status.HTTP_202_ACCEPTED)
async def batch_evaluation(
    execution_trace_ids: list[uuid.UUID],
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    """CTO refinement #12: Batch evaluation placeholder. Reserves architecture for future worker integration."""
    return {
        "status": "ACCEPTED",
        "message": f"Queued {len(execution_trace_ids)} traces for background batch evaluation.",
        "job_id": str(uuid.uuid4())
    }


@router.get("", summary="List evaluations", response_model=EvaluationListResponse)
async def list_evaluations(
    status: Optional[EvaluationStatus] = Query(default=None),
    grade: Optional[QualityGrade] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    svc = EvaluationService(db)
    return await svc.list_evaluations(ctx, status=status, grade=grade, page=page, page_size=page_size)


@router.get("/metrics", summary="Get aggregated metrics analytics")
async def get_metrics(
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    svc = EvaluationService(db)
    return await svc.get_metrics_analytics(ctx)


@router.get("/{id}", summary="Get evaluation details", response_model=EvaluationDetailResponse)
async def get_evaluation_detail(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    svc = EvaluationService(db)
    try:
        return await svc.get_evaluation_detail(ctx, id)
    except ValueError as val_err:
        raise HTTPException(status_code=404, detail=str(val_err))


@router.post("/feedback", summary="Submit human feedback for an evaluation", response_model=FeedbackResponse)
async def submit_feedback(
    body: FeedbackCreateRequest,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    svc = EvaluationService(db)
    try:
        feedback = await svc.record_feedback(
            ctx=ctx,
            evaluation_id=body.evaluation_id,
            feedback_type=body.feedback_type,
            feedback_category=body.feedback_category,
            rating=body.rating,
            comment=body.comment
        )
        return feedback
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
