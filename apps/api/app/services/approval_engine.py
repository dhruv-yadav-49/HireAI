import uuid
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


from app.core.context import RequestContext
from app.models.ai_plan import AIPlan
from app.models.ai_action import AIAction
from app.models.ai_approval import AIApproval
from app.models.enums import AIActionStatus, AIApprovalStatus, PlannerState
from app.services.execution_engine import ExecutionEngine


class ApprovalEngine:
    @classmethod
    async def approve_action(
        cls,
        db: AsyncSession,
        ctx: RequestContext,
        action_id: uuid.UUID,
        comment: Optional[str] = None
    ) -> AIPlan:
        """Approves a paused action and triggers immediate execution of the plan's next steps."""
        # Validate action tenant mapping
        action = await db.get(AIAction, action_id)
        if not action:
            raise ValueError("AI Action not found.")

        plan = await db.get(AIPlan, action.plan_id)
        if not plan or plan.organization_id != ctx.tenant_id:
            raise ValueError("AI Plan not found or inaccessible.")

        # Find approval
        stmt = select(AIApproval).where(
            AIApproval.action_id == action_id,
            AIApproval.status == AIApprovalStatus.PENDING
        )
        res = await db.execute(stmt)
        approval = res.scalar_one_or_none()
        if not approval:
            raise ValueError("No pending approval request found for this action.")

        # 1. Update Approval Record
        approval.status = AIApprovalStatus.APPROVED
        approval.approved_at = datetime.now(timezone.utc)
        approval.comment = comment

        # 2. Update Action Status to PENDING so execution engine will run it
        action.status = AIActionStatus.PENDING
        await db.flush()

        await ExecutionEngine.publish_event(ctx, "ai.approval.completed", {
            "plan_id": str(plan.id),
            "action_id": str(action.id),
            "approval_id": str(approval.id),
            "status": "APPROVED"
        })

        # 3. Resume Plan Execution
        updated_plan = await ExecutionEngine.execute_plan(db, ctx, plan.id)
        await db.commit()
        return updated_plan

    @classmethod
    async def reject_action(
        cls,
        db: AsyncSession,
        ctx: RequestContext,
        action_id: uuid.UUID,
        comment: Optional[str] = None
    ) -> AIPlan:
        """Rejects a paused action, terminating plan execution and setting status to FAILED."""
        action = await db.get(AIAction, action_id)
        if not action:
            raise ValueError("AI Action not found.")

        plan = await db.get(AIPlan, action.plan_id)
        if not plan or plan.organization_id != ctx.tenant_id:
            raise ValueError("AI Plan not found or inaccessible.")

        stmt = select(AIApproval).where(
            AIApproval.action_id == action_id,
            AIApproval.status == AIApprovalStatus.PENDING
        )
        res = await db.execute(stmt)
        approval = res.scalar_one_or_none()
        if not approval:
            raise ValueError("No pending approval request found for this action.")

        # 1. Update Approval
        approval.status = AIApprovalStatus.REJECTED
        approval.rejected_at = datetime.now(timezone.utc)
        approval.comment = comment

        # 2. Update Action & Plan
        action.status = AIActionStatus.REJECTED
        plan.status = PlannerState.FAILED
        await db.flush()

        await ExecutionEngine.publish_event(ctx, "ai.approval.completed", {
            "plan_id": str(plan.id),
            "action_id": str(action.id),
            "approval_id": str(approval.id),
            "status": "REJECTED"
        })
        await ExecutionEngine.publish_event(ctx, "ai.action.failed", {
            "plan_id": str(plan.id),
            "action_id": str(action.id),
            "reason": "Human override: approval rejected."
        })
        await ExecutionEngine.publish_event(ctx, "ai.execution.completed", {
            "plan_id": str(plan.id),
            "status": "FAILED"
        })

        await db.commit()
        return plan
