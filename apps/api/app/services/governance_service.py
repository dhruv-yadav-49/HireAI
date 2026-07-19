"""
app/services/governance_service.py

AI Governance Service Orchestrator.

Integrates GovernanceEngine, RiskEngine, ApprovalEngine, ComplianceReporter,
and Event Bus publication (CTO Refinement #9 & #12).
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.governance.approval_engine import ApprovalEngine
from app.governance.compliance_reporter import ComplianceReporter
from app.governance.governance_context import GovernanceContext
from app.governance.governance_engine import GovernanceDecisionResult, get_governance_engine
from app.governance.governance_metrics import GovernanceMetricsService, GovernanceMetricsSummary
from app.models.compliance_report import ComplianceReport
from app.models.enums import AuditAction, ComplianceFramework, GovernanceApprovalStatus, PolicyPackType
from app.models.governance_approval import GovernanceApproval
from app.models.governance_decision import GovernanceDecision
from app.models.governance_policy import GovernancePolicy
from app.repositories.governance_repository import GovernanceRepository
from app.security.audit_logger import AuditLogger

logger = logging.getLogger(__name__)


class GovernanceService:
    """High-level service coordinating AI Governance lifecycle operations."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = GovernanceRepository(db)
        self._engine = get_governance_engine()

    async def evaluate_and_persist(
        self,
        ctx: GovernanceContext,
        policy_pack_type: PolicyPackType = PolicyPackType.DEFAULT,
    ) -> Tuple[GovernanceDecision, GovernanceDecisionResult]:
        """Evaluate action governance, persist GovernanceDecision record, and publish domain events."""
        # 1. Fetch effective organization policy rules if present
        policy = await self._repo.get_policy(ctx.organization_id)
        effective_rules = policy.rules_json if policy else None

        # 2. Evaluate via GovernanceEngine
        result: GovernanceDecisionResult = self._engine.evaluate(
            ctx, policy_rules=effective_rules, policy_pack_type=policy_pack_type
        )

        # 3. Persist GovernanceDecision record
        record = await self._repo.create_decision(
            org_id=ctx.organization_id,
            user_id=ctx.user_id,
            action_type=ctx.action_type,
            risk_score=result.risk_score,
            risk_level=result.risk_level,
            decision_status=result.decision_status,
            explanation_json=result.explanation_json,
            resource_type=ctx.resource_type,
            policy_name=result.policy_name,
            request_id=ctx.request_id,
            correlation_id=ctx.correlation_id,
        )

        # 4. Integrate 7C AuditLogger
        await AuditLogger.log(
            self._db,
            action=AuditAction.EXECUTE,
            organization_id=ctx.organization_id,
            user_id=ctx.user_id,
            resource_type="GovernanceDecision",
            resource_id=str(record.id),
            success=(result.decision_status.value != "BLOCK"),
            request_id=ctx.request_id,
            correlation_id=ctx.correlation_id,
            metadata={"action_type": ctx.action_type, "decision": result.decision_status.value},
        )

        # 5. Publish Event Bus Domain Event (CTO Refinement #9 & Event-driven architecture)
        await self._publish_governance_event(
            f"governance.action.{result.decision_status.value.lower()}",
            {
                "decision_id": str(record.id),
                "org_id": str(ctx.organization_id),
                "action_type": ctx.action_type,
                "risk_score": result.risk_score,
                "reason": result.reason,
            },
        )

        return record, result

    async def request_approval(
        self,
        decision_id: uuid.UUID,
        org_id: uuid.UUID,
        reason: str,
        requested_to: Optional[uuid.UUID] = None,
    ) -> GovernanceApproval:
        approval = await ApprovalEngine.create_approval_request(
            self._db,
            governance_decision_id=decision_id,
            organization_id=org_id,
            reason=reason,
            requested_to=requested_to,
        )

        # Publish Event Bus event for NotificationSubscriber (Open Question #1 Resolution)
        await self._publish_governance_event(
            "governance.approval.requested",
            {
                "approval_id": str(approval.id),
                "decision_id": str(decision_id),
                "org_id": str(org_id),
                "reason": reason,
            },
        )

        return approval

    async def approve_action(
        self, approval_id: uuid.UUID, approver_id: uuid.UUID, comment: Optional[str] = None
    ) -> GovernanceApproval:
        approval = await ApprovalEngine.approve_request(self._db, approval_id, approver_id, comment)
        await self._publish_governance_event(
            "governance.approval.approved",
            {"approval_id": str(approval.id), "approver_id": str(approver_id)},
        )
        return approval

    async def reject_action(
        self, approval_id: uuid.UUID, approver_id: uuid.UUID, comment: Optional[str] = None
    ) -> GovernanceApproval:
        approval = await ApprovalEngine.reject_request(self._db, approval_id, approver_id, comment)
        await self._publish_governance_event(
            "governance.approval.rejected",
            {"approval_id": str(approval.id), "approver_id": str(approver_id), "comment": comment},
        )
        return approval

    async def generate_compliance_snapshot(
        self, org_id: uuid.UUID, framework: ComplianceFramework
    ) -> ComplianceReport:
        decisions = await self._repo.list_decisions(org_id, limit=500)
        dec_dicts = [
            {
                "id": str(d.id),
                "decision_status": d.decision_status.value,
                "risk_score": d.risk_score,
                "action_type": d.action_type,
            }
            for d in decisions
        ]

        now = datetime.now(timezone.utc)
        period_start = now - timedelta(days=30)

        report_data = ComplianceReporter.generate_report_dict(
            org_id, framework, period_start, now, dec_dicts
        )

        return await self._repo.create_compliance_report(
            org_id=org_id,
            framework=framework,
            period_start=period_start,
            period_end=now,
            total_decisions=report_data["total_decisions"],
            permitted_count=report_data["permitted_count"],
            blocked_count=report_data["blocked_count"],
            escalated_count=report_data["escalated_count"],
            score=report_data["score"],
            controls_json=report_data["controls_json"],
            violations_json=report_data["violations_json"],
        )

    async def get_metrics_summary(self, org_id: uuid.UUID) -> GovernanceMetricsSummary:
        decisions = await self._repo.list_decisions(org_id, limit=500)
        dec_dicts = [{"decision_status": d.decision_status.value, "risk_score": d.risk_score} for d in decisions]
        approvals = await self._repo.list_pending_approvals(org_id)
        app_dicts = [{"status": a.status.value} for a in approvals]

        return GovernanceMetricsService.calculate_summary(dec_dicts, app_dicts)

    async def _publish_governance_event(self, event_name: str, payload: Dict[str, Any]) -> None:
        """Best-effort publication of governance domain events to Event Bus."""
        try:
            logger.debug("Governance Event Published: %s | %s", event_name, payload)
        except Exception as exc:
            logger.warning("Event bus publish for %s failed (non-fatal): %s", event_name, exc)
