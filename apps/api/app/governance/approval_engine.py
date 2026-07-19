"""
app/governance/approval_engine.py

Human Approval Lifecycle & Lease Engine.

CTO Refinement #6: Lease-based job/approval ownership.
Supports requesting approval, acquiring/renewing leases, granting approval,
rejecting, and expiring stale approval requests.

ADR-022: Human Oversight — human approval is required for all escalated decisions.
"""
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.governance_approval import GovernanceApproval
from app.models.enums import GovernanceApprovalStatus, AuditAction
from app.security.audit_logger import AuditLogger

logger = logging.getLogger(__name__)

DEFAULT_LEASE_MINUTES = 15
DEFAULT_EXPIRY_HOURS = 24


class ApprovalEngine:
    """Manages approval workflow states, approval leases, and timeouts."""

    @staticmethod
    async def create_approval_request(
        db: AsyncSession,
        governance_decision_id: uuid.UUID,
        organization_id: uuid.UUID,
        reason: str,
        requested_to: Optional[uuid.UUID] = None,
        expiry_hours: int = DEFAULT_EXPIRY_HOURS,
    ) -> GovernanceApproval:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=expiry_hours)

        approval = GovernanceApproval(
            id=uuid.uuid4(),
            governance_decision_id=governance_decision_id,
            organization_id=organization_id,
            requested_to=requested_to,
            status=GovernanceApprovalStatus.PENDING,
            reason=reason,
            expires_at=expires_at,
            created_at=now,
        )
        db.add(approval)
        await db.flush()
        return approval

    @staticmethod
    async def acquire_lease(
        db: AsyncSession,
        approval_id: uuid.UUID,
        user_id: uuid.UUID,
        lease_minutes: int = DEFAULT_LEASE_MINUTES,
    ) -> bool:
        """Acquire or renew an approval lease for a reviewer.

        Returns True if lease acquired successfully, False if already held by another active user.
        """
        now = datetime.now(timezone.utc)
        lease_until = now + timedelta(minutes=lease_minutes)

        stmt = select(GovernanceApproval).where(GovernanceApproval.id == approval_id)
        result = await db.execute(stmt)
        approval = result.scalar_one_or_none()

        if not approval or approval.status != GovernanceApprovalStatus.PENDING:
            return False

        # Can acquire if lease is unheld, expired, or held by self
        if approval.leased_by is None or approval.lease_until is None or approval.lease_until < now or approval.leased_by == user_id:
            approval.leased_by = user_id
            approval.lease_until = lease_until
            await db.flush()
            return True

        return False

    @staticmethod
    async def approve_request(
        db: AsyncSession,
        approval_id: uuid.UUID,
        approver_id: uuid.UUID,
        comment: Optional[str] = None,
    ) -> GovernanceApproval:
        now = datetime.now(timezone.utc)
        stmt = select(GovernanceApproval).where(GovernanceApproval.id == approval_id)
        result = await db.execute(stmt)
        approval = result.scalar_one_or_none()

        if not approval:
            raise ValueError(f"Approval request {approval_id} not found.")

        if approval.status != GovernanceApprovalStatus.PENDING:
            raise ValueError(f"Approval request is in {approval.status.value} state.")

        approval.status = GovernanceApprovalStatus.APPROVED
        approval.approver_id = approver_id
        approval.approved_at = now
        approval.comment = comment
        approval.leased_by = None
        approval.lease_until = None

        await db.flush()

        # Audit log integration (7C)
        await AuditLogger.log(
            db,
            action=AuditAction.UPDATE,
            organization_id=approval.organization_id,
            user_id=approver_id,
            resource_type="GovernanceApproval",
            resource_id=str(approval.id),
            success=True,
            metadata={"decision": "APPROVED", "comment": comment},
        )

        return approval

    @staticmethod
    async def reject_request(
        db: AsyncSession,
        approval_id: uuid.UUID,
        approver_id: uuid.UUID,
        comment: Optional[str] = None,
    ) -> GovernanceApproval:
        now = datetime.now(timezone.utc)
        stmt = select(GovernanceApproval).where(GovernanceApproval.id == approval_id)
        result = await db.execute(stmt)
        approval = result.scalar_one_or_none()

        if not approval:
            raise ValueError(f"Approval request {approval_id} not found.")

        if approval.status != GovernanceApprovalStatus.PENDING:
            raise ValueError(f"Approval request is in {approval.status.value} state.")

        approval.status = GovernanceApprovalStatus.REJECTED
        approval.approver_id = approver_id
        approval.rejected_at = now
        approval.comment = comment
        approval.leased_by = None
        approval.lease_until = None

        await db.flush()

        # Audit log integration (7C)
        await AuditLogger.log(
            db,
            action=AuditAction.UPDATE,
            organization_id=approval.organization_id,
            user_id=approver_id,
            resource_type="GovernanceApproval",
            resource_id=str(approval.id),
            success=True,
            metadata={"decision": "REJECTED", "comment": comment},
        )

        return approval

    @staticmethod
    async def expire_stale_approvals(db: AsyncSession) -> int:
        """Batch expire all PENDING approvals past their expires_at date."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(GovernanceApproval)
            .where(
                GovernanceApproval.status == GovernanceApprovalStatus.PENDING,
                GovernanceApproval.expires_at < now,
            )
            .values(
                status=GovernanceApprovalStatus.EXPIRED,
                leased_by=None,
                lease_until=None,
            )
        )
        res = await db.execute(stmt)
        await db.flush()
        return res.rowcount
