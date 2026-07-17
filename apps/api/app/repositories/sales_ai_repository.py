import uuid
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.context import RequestContext
from app.models.ai_plan import AIPlan
from app.models.ai_action import AIAction
from app.models.ai_approval import AIApproval


class SalesAIRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_plan(self, plan: AIPlan) -> AIPlan:
        self.db.add(plan)
        await self.db.flush()
        return plan

    async def get_plan_by_id(self, ctx: RequestContext, plan_id: uuid.UUID) -> AIPlan | None:
        result = await self.db.execute(
            select(AIPlan).where(
                AIPlan.id == plan_id,
                AIPlan.organization_id == ctx.tenant_id
            )
        )
        return result.scalar_one_or_none()

    async def list_plans(
        self,
        ctx: RequestContext,
        lead_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[list[AIPlan], int]:
        stmt = select(AIPlan).where(AIPlan.organization_id == ctx.tenant_id)
        if lead_id is not None:
            stmt = stmt.where(AIPlan.lead_id == lead_id)
        if status is not None:
            stmt = stmt.where(AIPlan.status == status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        stmt = stmt.order_by(AIPlan.created_at.desc()).offset(offset).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def create_action(self, action: AIAction) -> AIAction:
        self.db.add(action)
        await self.db.flush()
        return action

    async def get_action_by_id(self, ctx: RequestContext, action_id: uuid.UUID) -> AIAction | None:
        result = await self.db.execute(
            select(AIAction)
            .join(AIPlan, AIAction.plan_id == AIPlan.id)
            .where(
                AIAction.id == action_id,
                AIPlan.organization_id == ctx.tenant_id
            )
        )
        return result.scalar_one_or_none()

    async def list_actions(
        self,
        ctx: RequestContext,
        plan_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[list[AIAction], int]:
        stmt = select(AIAction).join(AIPlan, AIAction.plan_id == AIPlan.id).where(AIPlan.organization_id == ctx.tenant_id)
        if plan_id is not None:
            stmt = stmt.where(AIAction.plan_id == plan_id)
        if status is not None:
            stmt = stmt.where(AIAction.status == status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        stmt = stmt.order_by(AIAction.created_at.asc()).offset(offset).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def create_approval(self, approval: AIApproval) -> AIApproval:
        self.db.add(approval)
        await self.db.flush()
        return approval

    async def get_approval_by_action_id(self, ctx: RequestContext, action_id: uuid.UUID) -> AIApproval | None:
        result = await self.db.execute(
            select(AIApproval)
            .join(AIAction, AIApproval.action_id == AIAction.id)
            .join(AIPlan, AIAction.plan_id == AIPlan.id)
            .where(
                AIApproval.action_id == action_id,
                AIPlan.organization_id == ctx.tenant_id
            )
        )
        return result.scalar_one_or_none()
