"""
app/security/audit_logger.py

Append-only security audit trail.

ADR-021: Immutable Audit — records are written once, never modified.
CTO refinement #6: request_id, correlation_id, success, duration_ms allow
audit events to be correlated with execution traces, jobs, and Event Bus events.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.enums import AuditAction

logger = logging.getLogger(__name__)


class AuditLogger:
    """Stateless append-only audit logger.

    Always flush() — never commit(). The caller owns the transaction.
    This ensures audit records are written in the same transaction as the
    operation they record.
    """

    @staticmethod
    async def log(
        db: AsyncSession,
        action: AuditAction,
        *,
        organization_id: Optional[uuid.UUID] = None,
        user_id: Optional[uuid.UUID] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        success: bool = True,
        duration_ms: Optional[int] = None,
        request_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """Create and persist an immutable audit record.

        Returns the created AuditLog (unflushed session — caller commits).
        """
        record = AuditLog(
            id=uuid.uuid4(),
            organization_id=organization_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            success=success,
            duration_ms=duration_ms,
            request_id=request_id,
            correlation_id=correlation_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata_json=metadata,
            created_at=datetime.now(timezone.utc),
        )
        db.add(record)
        await db.flush()
        return record

    # ── Convenience shortcuts ──────────────────────────────────────────────────

    @staticmethod
    async def log_login(
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        organization_id: Optional[uuid.UUID],
        success: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        return await AuditLogger.log(
            db,
            AuditAction.LOGIN,
            organization_id=organization_id,
            user_id=user_id,
            resource_type="User",
            resource_id=str(user_id),
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            metadata=metadata,
        )

    @staticmethod
    async def log_api_key_access(
        db: AsyncSession,
        *,
        api_key_id: uuid.UUID,
        organization_id: uuid.UUID,
        success: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        scope_used: Optional[str] = None,
    ) -> AuditLog:
        return await AuditLogger.log(
            db,
            AuditAction.EXECUTE,
            organization_id=organization_id,
            resource_type="APIKey",
            resource_id=str(api_key_id),
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            metadata={"scope": scope_used} if scope_used else None,
        )

    @staticmethod
    async def log_api_key_rotation(
        db: AsyncSession,
        *,
        api_key_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        request_id: Optional[str] = None,
    ) -> AuditLog:
        return await AuditLogger.log(
            db,
            AuditAction.ROTATE,
            organization_id=organization_id,
            user_id=user_id,
            resource_type="APIKey",
            resource_id=str(api_key_id),
            success=True,
            request_id=request_id,
        )

    @staticmethod
    async def log_policy_change(
        db: AsyncSession,
        *,
        policy_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        action: AuditAction = AuditAction.UPDATE,
        request_id: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        return await AuditLogger.log(
            db,
            action,
            organization_id=organization_id,
            user_id=user_id,
            resource_type="SecurityPolicy",
            resource_id=str(policy_id),
            success=True,
            request_id=request_id,
            metadata=changes,
        )

    @staticmethod
    async def log_authorization_denied(
        db: AsyncSession,
        *,
        organization_id: Optional[uuid.UUID],
        user_id: Optional[uuid.UUID],
        resource_type: str,
        action: str,
        reason: str,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        return await AuditLogger.log(
            db,
            AuditAction.DENIED,
            organization_id=organization_id,
            user_id=user_id,
            resource_type=resource_type,
            success=False,
            request_id=request_id,
            ip_address=ip_address,
            metadata={"action": action, "reason": reason},
        )
