"""
app/governance/action_interceptor.py

FastAPI Action Interceptor Dependency Hook.

Provides a clean, non-breaking guard function for AI job / action submission routes.
Intercepts action submission, builds GovernanceContext, evaluates via GovernanceEngine,
and enforces PERMIT (proceed), BLOCK (raise 403), or ESCALATE (raise 202 / return approval_required).

ADR-022: Governance by Composition — wraps endpoints without modifying route internals.
"""
from typing import Dict, Any, Optional
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.governance.governance_context import build_governance_context
from app.governance.governance_engine import get_governance_engine
from app.models.enums import GovernanceDecisionStatus
from app.security.security_context import SecurityContext
from app.services.governance_service import GovernanceService


class ActionInterceptor:
    """FastAPI Interceptor for AI actions."""

    @staticmethod
    async def check_action(
        db: AsyncSession,
        sec_ctx: SecurityContext,
        action_type: str,
        action_payload: Optional[Dict[str, Any]] = None,
        job_type: Optional[str] = None,
        agent_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Check an AI action against governance policy before execution.

        Raises:
            HTTPException(403) if status is BLOCK.
            HTTPException(202) if status is ESCALATE (requires approval).

        Returns dict summary if PERMIT.
        """
        gov_ctx = build_governance_context(
            security_context=sec_ctx,
            action_type=action_type,
            action_payload=action_payload or {},
            job_type=job_type,
            agent_type=agent_type,
        )

        service = GovernanceService(db)
        decision_record, result = await service.evaluate_and_persist(gov_ctx)

        if result.decision_status == GovernanceDecisionStatus.BLOCK:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "GovernanceBlock",
                    "message": result.reason,
                    "risk_score": result.risk_score,
                    "decision_id": str(decision_record.id),
                },
            )

        if result.decision_status == GovernanceDecisionStatus.ESCALATE:
            # Create approval request
            approval = await service.request_approval(
                decision_id=decision_record.id,
                org_id=gov_ctx.organization_id,
                reason=result.reason,
            )
            raise HTTPException(
                status_code=202,
                detail={
                    "message": "Action escalated for human approval.",
                    "approval_required": True,
                    "approval_id": str(approval.id),
                    "decision_id": str(decision_record.id),
                    "risk_score": result.risk_score,
                },
            )

        return {
            "status": "PERMIT",
            "decision_id": str(decision_record.id),
            "risk_score": result.risk_score,
        }
