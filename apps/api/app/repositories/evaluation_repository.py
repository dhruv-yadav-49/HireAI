import uuid
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.enums import EvaluationStatus, QualityGrade
from app.models.ai_evaluation import AIEvaluation
from app.models.ai_evaluation_metric import AIEvaluationMetric
from app.models.ai_feedback import AIFeedback
from app.models.ai_quality_rule import AIQualityRule


class EvaluationRepository:
    """Handles multi-tenant isolated database queries for all quality evaluation metrics and customer feedback."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_evaluations(
        self,
        ctx: RequestContext,
        status: Optional[EvaluationStatus] = None,
        grade: Optional[QualityGrade] = None,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[list[AIEvaluation], int]:
        stmt = select(AIEvaluation).where(AIEvaluation.organization_id == ctx.tenant_id)
        if status:
            stmt = stmt.where(AIEvaluation.status == status)
        if grade:
            stmt = stmt.where(AIEvaluation.quality_grade == grade)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_res = await self.db.execute(count_stmt)
        total = count_res.scalar() or 0

        stmt = stmt.order_by(AIEvaluation.created_at.desc())
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def get_evaluation(
        self,
        ctx: RequestContext,
        evaluation_id: uuid.UUID
    ) -> Optional[AIEvaluation]:
        result = await self.db.execute(
            select(AIEvaluation).where(
                AIEvaluation.id == evaluation_id,
                AIEvaluation.organization_id == ctx.tenant_id
            )
        )
        return result.scalar_one_or_none()

    async def get_metrics(
        self,
        evaluation_id: uuid.UUID
    ) -> list[AIEvaluationMetric]:
        result = await self.db.execute(
            select(AIEvaluationMetric).where(
                AIEvaluationMetric.evaluation_id == evaluation_id
            )
        )
        return list(result.scalars().all())

    async def list_quality_rules(
        self,
        ctx: RequestContext
    ) -> list[AIQualityRule]:
        result = await self.db.execute(
            select(AIQualityRule).where(
                AIQualityRule.organization_id == ctx.tenant_id
            )
        )
        return list(result.scalars().all())
