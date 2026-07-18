import uuid
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.enums import SuggestionStatus, LearningStatus
from app.models.ai_learning_dataset import AILearningDataset
from app.models.ai_improvement import AIImprovement
from app.models.ai_prompt_suggestion import AIPromptSuggestion
from app.models.ai_policy_suggestion import AIPolicySuggestion


class LearningRepository:
    """Handles multi-tenant isolated database queries for all learning datasets, optimization, and suggestions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_datasets(
        self,
        ctx: RequestContext,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[list[AILearningDataset], int]:
        stmt = select(AILearningDataset).where(AILearningDataset.organization_id == ctx.tenant_id)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_res = await self.db.execute(count_stmt)
        total = count_res.scalar() or 0

        stmt = stmt.order_by(AILearningDataset.created_at.desc())
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def list_improvements(
        self,
        ctx: RequestContext,
        status: Optional[SuggestionStatus] = None,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[list[AIImprovement], int]:
        stmt = select(AIImprovement).where(AIImprovement.organization_id == ctx.tenant_id)
        if status:
            stmt = stmt.where(AIImprovement.status == status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_res = await self.db.execute(count_stmt)
        total = count_res.scalar() or 0

        stmt = stmt.order_by(AIImprovement.created_at.desc())
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def get_prompt_suggestion(
        self,
        ctx: RequestContext,
        suggestion_id: uuid.UUID
    ) -> Optional[AIPromptSuggestion]:
        result = await self.db.execute(
            select(AIPromptSuggestion).where(
                AIPromptSuggestion.id == suggestion_id,
                AIPromptSuggestion.organization_id == ctx.tenant_id
            )
        )
        return result.scalar_one_or_none()

    async def get_policy_suggestion(
        self,
        ctx: RequestContext,
        suggestion_id: uuid.UUID
    ) -> Optional[AIPolicySuggestion]:
        result = await self.db.execute(
            select(AIPolicySuggestion).where(
                AIPolicySuggestion.id == suggestion_id,
                AIPolicySuggestion.organization_id == ctx.tenant_id
            )
        )
        return result.scalar_one_or_none()
