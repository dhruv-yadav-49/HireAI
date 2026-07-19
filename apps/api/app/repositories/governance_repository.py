"""
app/repositories/governance_repository.py

Data access layer for all Sprint 7D Governance models.
"""
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compliance_report import ComplianceReport
from app.models.enums import ComplianceFramework, GovernanceApprovalStatus, GovernanceDecisionStatus, PolicyPackType, RiskLevel, ViolationSeverity
from app.models.governance_approval import GovernanceApproval
from app.models.governance_decision import GovernanceDecision
from app.models.governance_policy import GovernancePolicy
from app.models.policy_violation import PolicyViolation


class GovernanceRepository:
    """Repository for AI Governance data models."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Governance Policy ──────────────────────────────────────────────────────

    async def get_policy(self, org_id: uuid.UUID) -> Optional[GovernancePolicy]:
        stmt = (
            select(GovernancePolicy)
            .where(
                GovernancePolicy.organization_id == org_id,
                GovernancePolicy.enabled.is_(True),
            )
            .order_by(GovernancePolicy.version.desc())
            .limit(1)
        )
        res = await self._db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_default_policy(self) -> Optional[GovernancePolicy]:
        stmt = (
            select(GovernancePolicy)
            .where(
                GovernancePolicy.organization_id.is_(None),
                GovernancePolicy.enabled.is_(True),
            )
            .order_by(GovernancePolicy.version.desc())
            .limit(1)
        )
        res = await self._db.execute(stmt)
        return res.scalar_one_or_none()

    async def create_policy_version(
        self,
        org_id: Optional[uuid.UUID],
        pack_type: PolicyPackType,
        rules: Dict[str, Any],
        version: int = 1,
    ) -> GovernancePolicy:
        policy = GovernancePolicy(
            id=uuid.uuid4(),
            organization_id=org_id,
            pack_type=pack_type,
            version=version,
            published_at=datetime.now(timezone.utc),
            rules_json=rules,
            enabled=True,
            created_at=datetime.now(timezone.utc),
        )
        self._db.add(policy)
        await self._db.flush()
        return policy

    # ── Governance Decision ────────────────────────────────────────────────────

    async def create_decision(
        self,
        org_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        action_type: str,
        risk_score: float,
        risk_level: RiskLevel,
        decision_status: GovernanceDecisionStatus,
        explanation_json: Dict[str, Any],
        resource_type: Optional[str] = None,
        action_payload_hash: Optional[str] = None,
        policy_name: Optional[str] = None,
        request_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> GovernanceDecision:
        record = GovernanceDecision(
            id=uuid.uuid4(),
            organization_id=org_id,
            user_id=user_id,
            action_type=action_type,
            resource_type=resource_type,
            action_payload_hash=action_payload_hash,
            risk_score=risk_score,
            risk_level=risk_level,
            decision_status=decision_status,
            explanation_json=explanation_json,
            policy_name=policy_name,
            request_id=request_id,
            correlation_id=correlation_id,
            decided_at=datetime.now(timezone.utc),
        )
        self._db.add(record)
        await self._db.flush()
        return record

    async def list_decisions(
        self,
        org_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> List[GovernanceDecision]:
        stmt = (
            select(GovernanceDecision)
            .where(GovernanceDecision.organization_id == org_id)
            .order_by(GovernanceDecision.decided_at.desc())
            .limit(limit)
            .offset(offset)
        )
        res = await self._db.execute(stmt)
        return list(res.scalars().all())

    # ── Governance Approvals ───────────────────────────────────────────────────

    async def list_pending_approvals(self, org_id: uuid.UUID) -> List[GovernanceApproval]:
        stmt = (
            select(GovernanceApproval)
            .where(
                GovernanceApproval.organization_id == org_id,
                GovernanceApproval.status == GovernanceApprovalStatus.PENDING,
            )
            .order_by(GovernanceApproval.created_at.desc())
        )
        res = await self._db.execute(stmt)
        return list(res.scalars().all())

    # ── Compliance Reports & Violations ───────────────────────────────────────

    async def create_compliance_report(
        self,
        org_id: uuid.UUID,
        framework: ComplianceFramework,
        period_start: datetime,
        period_end: datetime,
        total_decisions: int,
        permitted_count: int,
        blocked_count: int,
        escalated_count: int,
        score: float,
        controls_json: Dict[str, Any],
        violations_json: Dict[str, Any],
    ) -> ComplianceReport:
        report = ComplianceReport(
            id=uuid.uuid4(),
            organization_id=org_id,
            framework=framework,
            period_start=period_start,
            period_end=period_end,
            total_decisions=total_decisions,
            permitted_count=permitted_count,
            blocked_count=blocked_count,
            escalated_count=escalated_count,
            score=score,
            controls_json=controls_json,
            violations_json=violations_json,
            generated_at=datetime.now(timezone.utc),
        )
        self._db.add(report)
        await self._db.flush()
        return report

    async def list_compliance_reports(self, org_id: uuid.UUID) -> List[ComplianceReport]:
        stmt = (
            select(ComplianceReport)
            .where(ComplianceReport.organization_id == org_id)
            .order_by(ComplianceReport.generated_at.desc())
        )
        res = await self._db.execute(stmt)
        return list(res.scalars().all())
