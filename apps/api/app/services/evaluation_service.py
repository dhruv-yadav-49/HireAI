import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.context import RequestContext
from app.core.events import DomainEvent, get_event_publisher
from app.models.enums import EvaluationStatus, QualityGrade, FeedbackType, FeedbackCategory
from app.models.ai_evaluation import AIEvaluation
from app.models.ai_evaluation_metric import AIEvaluationMetric
from app.models.ai_feedback import AIFeedback
from app.models.ai_quality_rule import AIQualityRule
from app.repositories.evaluation_repository import EvaluationRepository
from app.services.evaluation_engine import EvaluationEngine


class EvaluationService:
    """Orchestrates quality evaluation pipelines, quality rules, and user feedback records."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = EvaluationRepository(db)

    async def _publish(self, ctx: RequestContext, event_name: str, payload: dict) -> None:
        event = DomainEvent(
            event_name=event_name,
            tenant_id=ctx.tenant_id,
            request_id=ctx.request_id,
            actor_id=ctx.user.id if ctx.user else None,
            payload=payload
        )
        try:
            pub = get_event_publisher()
            await pub.publish(event)
        except Exception:
            pass

    async def trigger_evaluation(
        self,
        ctx: RequestContext,
        execution_trace_id: uuid.UUID
    ) -> AIEvaluation:
        """Triggers the evaluation engine for a trace."""
        # Ensure trace exists and is owned by organization
        from app.models.ai_execution_trace import AIExecutionTrace
        trace = await self.db.get(AIExecutionTrace, execution_trace_id)
        if not trace or trace.organization_id != ctx.tenant_id:
            raise ValueError("Execution trace not found or unauthorized.")

        evaluation = await EvaluationEngine.evaluate_execution(self.db, execution_trace_id)
        return evaluation

    async def list_evaluations(
        self,
        ctx: RequestContext,
        status: Optional[EvaluationStatus] = None,
        grade: Optional[QualityGrade] = None,
        page: int = 1,
        page_size: int = 20
    ) -> dict:
        items, total = await self.repo.list_evaluations(ctx, status, grade, page, page_size)
        return {
            "items": [
                {
                    "id": str(e.id),
                    "execution_trace_id": str(e.execution_trace_id),
                    "agent_type": e.agent_type.value,
                    "status": e.status.value,
                    "overall_score": e.overall_score,
                    "quality_grade": e.quality_grade.value if e.quality_grade else None,
                    "summary": e.summary,
                    "evaluation_version": e.evaluation_version,
                    "eligible_for_training": e.eligible_for_training,
                    "created_at": e.created_at.isoformat() if e.created_at else None
                }
                for e in items
            ],
            "total": total,
            "page": page,
            "page_size": page_size
        }

    async def get_evaluation_detail(
        self,
        ctx: RequestContext,
        evaluation_id: uuid.UUID
    ) -> dict:
        e = await self.repo.get_evaluation(ctx, evaluation_id)
        if not e:
            raise ValueError("Evaluation not found or unauthorized.")

        metrics = await self.repo.get_metrics(evaluation_id)

        return {
            "summary": {
                "id": str(e.id),
                "execution_trace_id": str(e.execution_trace_id),
                "agent_type": e.agent_type.value,
                "status": e.status.value,
                "overall_score": e.overall_score,
                "quality_grade": e.quality_grade.value if e.quality_grade else None,
                "summary": e.summary,
                "evaluation_version": e.evaluation_version,
                "evaluation_model": e.evaluation_model,
                "evaluation_trace": e.evaluation_trace,
                "evaluation_timeline": e.evaluation_timeline,
                "eligible_for_training": e.eligible_for_training,
                "created_at": e.created_at.isoformat() if e.created_at else None
            },
            "metrics": [
                {
                    "metric_type": m.metric_type.value,
                    "score": m.score,
                    "weight": m.weight,
                    "details": m.details_json
                }
                for m in metrics
            ]
        }

    async def record_feedback(
        self,
        ctx: RequestContext,
        evaluation_id: uuid.UUID,
        feedback_type: FeedbackType,
        feedback_category: FeedbackCategory = FeedbackCategory.OTHER,
        rating: Optional[int] = None,
        comment: Optional[str] = None
    ) -> AIFeedback:
        """Records user feedback for an evaluation."""
        e = await self.repo.get_evaluation(ctx, evaluation_id)
        if not e:
            raise ValueError("Evaluation not found or unauthorized.")

        feedback = AIFeedback(
            evaluation_id=evaluation_id,
            user_id=ctx.user.id if ctx.user else None,
            feedback_type=feedback_type,
            feedback_category=feedback_category,
            rating=rating,
            comment=comment
        )
        self.db.add(feedback)
        await self.db.flush()

        await self._publish(ctx, "feedback.received", {
            "feedback_id": str(feedback.id),
            "evaluation_id": str(evaluation_id),
            "feedback_type": feedback_type.value,
            "feedback_category": feedback_category.value
        })

        return feedback

    async def get_metrics_analytics(
        self,
        ctx: RequestContext
    ) -> dict:
        """Aggregates average scores across all metrics for the organization."""
        # Query total count
        stmt = select(AIEvaluation.id).where(AIEvaluation.organization_id == ctx.tenant_id)
        res = await self.db.execute(stmt)
        ids = [r[0] for r in res.fetchall()]

        if not ids:
            return {"total_evaluations": 0, "averages": {}}

        # Average metric scores
        metric_stmt = select(
            AIEvaluationMetric.metric_type,
            func.avg(AIEvaluationMetric.score),
            func.count(AIEvaluationMetric.id)
        ).where(
            AIEvaluationMetric.evaluation_id.in_(ids)
        ).group_by(AIEvaluationMetric.metric_type)

        metric_res = await self.db.execute(metric_stmt)
        averages = {
            row[0].value: round(float(row[1]), 2)
            for row in metric_res.fetchall()
        }

        # Quality Grade distribution
        grade_stmt = select(
            AIEvaluation.quality_grade,
            func.count(AIEvaluation.id)
        ).where(
            AIEvaluation.id.in_(ids)
        ).group_by(AIEvaluation.quality_grade)

        grade_res = await self.db.execute(grade_stmt)
        grade_dist = {
            row[0].value if row[0] else "UNKNOWN": row[1]
            for row in grade_res.fetchall()
        }

        return {
            "total_evaluations": len(ids),
            "metric_averages": averages,
            "grade_distribution": grade_dist
        }
