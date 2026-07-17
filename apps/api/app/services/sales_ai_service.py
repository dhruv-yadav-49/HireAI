import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.ai_plan import AIPlan
from app.models.ai_action import AIAction
from app.repositories.sales_ai_repository import SalesAIRepository
from app.services.reasoning_engine import ReasoningEngine
from app.services.planner import Planner
from app.services.execution_engine import ExecutionEngine
from app.services.approval_engine import ApprovalEngine


class SalesAIService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = SalesAIRepository(db)

    async def analyze_lead(
        self,
        ctx: RequestContext,
        lead_id: uuid.UUID,
        goal: Optional[str] = None
    ) -> dict:
        """Runs the reasoning engine to analyze the lead stage, deterministic strategy, and memory."""
        return await ReasoningEngine.analyze_lead(self.db, ctx, lead_id, goal=goal or "Analyze lead status.")

    async def create_plan(
        self,
        ctx: RequestContext,
        lead_id: uuid.UUID,
        goal: str,
        conversation_id: Optional[uuid.UUID] = None
    ) -> AIPlan:
        """Generates and persists a generic multi-step plan for the lead goal."""
        plan = await Planner.create_plan(self.db, ctx, lead_id, goal, conversation_id=conversation_id)
        await self.db.commit()
        return plan

    async def execute_plan(self, ctx: RequestContext, plan_id: uuid.UUID) -> AIPlan:
        """Initializes and runs the execution actions queue against safety policies."""
        plan = await ExecutionEngine.execute_plan(self.db, ctx, plan_id)
        await self.db.commit()
        return plan

    async def approve_action(self, ctx: RequestContext, action_id: uuid.UUID, comment: Optional[str] = None) -> AIPlan:
        """Resolves action override approval, resuming execution loop."""
        return await ApprovalEngine.approve_action(self.db, ctx, action_id, comment=comment)

    async def reject_action(self, ctx: RequestContext, action_id: uuid.UUID, comment: Optional[str] = None) -> AIPlan:
        """Resolves action override rejection, terminating execution queue."""
        return await ApprovalEngine.reject_action(self.db, ctx, action_id, comment=comment)

    async def list_plans(
        self,
        ctx: RequestContext,
        lead_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[list[AIPlan], int]:
        return await self.repo.list_plans(ctx, lead_id=lead_id, status=status, page=page, page_size=page_size)

    async def list_actions(
        self,
        ctx: RequestContext,
        plan_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[list[AIAction], int]:
        return await self.repo.list_actions(ctx, plan_id=plan_id, status=status, page=page, page_size=page_size)
