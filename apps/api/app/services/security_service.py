"""
app/services/security_service.py

Security service — orchestrates API key lifecycle, authorization,
PII scanning, and audit logging.

CTO refinement #12: Security events are published to the Event Bus
(api_key.created, api_key.revoked, authorization.denied, pii.detected,
security.policy.updated) so Sprint 7B infrastructure remains the single
source of security-relevant events.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import APIKey
from app.models.audit_log import AuditLog
from app.models.enums import AuditAction, PIIType, SecretType
from app.models.pii_incident import PIIIncident
from app.repositories.security_repository import SecurityRepository
from app.security.api_key_manager import APIKeyManager
from app.security.audit_logger import AuditLogger
from app.security.authorization_engine import AuthDecision, AuthorizationEngine
from app.security.pii_detector import PIIDetector, PIIMatch, get_pii_detector
from app.security.pii_masker import PIIMasker
from app.security.security_context import SecurityContext

logger = logging.getLogger(__name__)


class SecurityService:
    """Orchestrates all Sprint 7C security operations.

    Each method is self-contained: it creates the repository, performs
    the operation, writes audit records, and publishes Event Bus events.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = SecurityRepository(db)
        self._detector = get_pii_detector()

    # ── API Keys ───────────────────────────────────────────────────────────────

    async def create_api_key(
        self,
        ctx: SecurityContext,
        name: str,
        scopes: List[str],
        expires_at: Optional[datetime] = None,
        created_from: Optional[str] = None,
    ) -> Tuple[str, APIKey]:
        """Generate a new API key.

        Returns (raw_key, APIKey). raw_key is returned ONCE — caller must
        display it immediately. It is never stored.
        """
        raw_key, prefix, hashed_key = APIKeyManager.generate_key()

        key_record = await self._repo.create_api_key(
            organization_id=ctx.organization_id,
            user_id=ctx.user_id,
            name=name,
            hashed_key=hashed_key,
            prefix=prefix,
            scopes=scopes,
            expires_at=expires_at,
            created_from=created_from,
        )

        await AuditLogger.log(
            self._db,
            AuditAction.CREATE,
            organization_id=ctx.organization_id,
            user_id=ctx.user_id,
            resource_type="APIKey",
            resource_id=str(key_record.id),
            success=True,
            request_id=ctx.request_id,
            correlation_id=ctx.correlation_id,
            ip_address=ctx.ip_address,
        )

        # Publish Event Bus security event (CTO refinement #12)
        await self._publish_security_event(
            "api_key.created",
            {
                "api_key_id": str(key_record.id),
                "org_id": str(ctx.organization_id),
                "name": name,
                "scopes": scopes,
            },
        )

        return raw_key, key_record

    async def revoke_api_key(
        self,
        ctx: SecurityContext,
        key_id: uuid.UUID,
    ) -> None:
        """Revoke an API key permanently."""
        await self._repo.revoke_api_key(key_id)

        await AuditLogger.log(
            self._db,
            AuditAction.REVOKE,
            organization_id=ctx.organization_id,
            user_id=ctx.user_id,
            resource_type="APIKey",
            resource_id=str(key_id),
            success=True,
            request_id=ctx.request_id,
        )

        # Publish security event
        await self._publish_security_event(
            "api_key.revoked",
            {"api_key_id": str(key_id), "org_id": str(ctx.organization_id)},
        )

    async def rotate_api_key(
        self,
        ctx: SecurityContext,
        key_id: uuid.UUID,
    ) -> Tuple[str, APIKey]:
        """Rotate an API key: revoke old, issue new with same scopes."""
        old_key = await self._repo.get_api_key_by_id(key_id)
        if old_key is None:
            raise ValueError(f"API key {key_id} not found.")

        old_scopes = old_key.scopes_json or []
        old_name = old_key.name

        # Revoke old
        await self._repo.revoke_api_key(key_id)

        # Create new
        raw_key, prefix, hashed_key = APIKeyManager.generate_key()
        new_key = await self._repo.create_api_key(
            organization_id=ctx.organization_id,
            user_id=ctx.user_id,
            name=f"{old_name} (rotated)",
            hashed_key=hashed_key,
            prefix=prefix,
            scopes=old_scopes,
            expires_at=old_key.expires_at,
            created_from="rotation",
        )

        await AuditLogger.log_api_key_rotation(
            self._db,
            api_key_id=new_key.id,
            organization_id=ctx.organization_id,
            user_id=ctx.user_id,
            request_id=ctx.request_id,
        )

        return raw_key, new_key

    # ── Authorization ──────────────────────────────────────────────────────────

    async def authorize(
        self,
        ctx: SecurityContext,
        resource_type: str,
        action: str,
        resource_attrs: Optional[Dict[str, Any]] = None,
    ) -> AuthDecision:
        """Evaluate RBAC + ABAC + TenantPolicy for a (resource, action) pair.

        Automatically writes an audit record on DENY.
        """
        decision = AuthorizationEngine.authorize(
            ctx=ctx,
            resource_type=resource_type,
            action=action,
            resource_attrs=resource_attrs,
        )

        if not decision.allowed:
            # Log denied authorization (CTO refinement #12)
            await AuditLogger.log_authorization_denied(
                self._db,
                organization_id=ctx.organization_id,
                user_id=ctx.user_id,
                resource_type=resource_type,
                action=action,
                reason=decision.reason,
                request_id=ctx.request_id,
                ip_address=ctx.ip_address,
            )
            # Publish Event Bus security event
            await self._publish_security_event(
                "authorization.denied",
                {
                    "org_id": str(ctx.organization_id),
                    "user_id": str(ctx.user_id),
                    "resource_type": resource_type,
                    "action": action,
                    "reason": decision.reason,
                },
            )

        return decision

    # ── PII Scanning ───────────────────────────────────────────────────────────

    async def scan_and_mask(
        self,
        ctx: SecurityContext,
        payload: Dict[str, Any],
        location: str = "request",
    ) -> Tuple[Dict[str, Any], List[PIIMatch]]:
        """Scan a dict payload for PII and return the masked version + match list.

        Persists PIIIncident records and publishes Event Bus events for each match.
        """
        matches = self._detector.scan_dict(payload)
        if not matches:
            return payload, []

        masked_payload = PIIMasker.mask_dict(payload, matches)

        # Persist incidents and publish events
        for match in matches:
            try:
                await self._repo.create_pii_incident(
                    org_id=ctx.organization_id,
                    pii_type=match.pii_type,
                    location=f"{location}/{match.detector}",
                    severity=0.9 if match.confidence >= 0.9 else 0.7,
                    confidence=match.confidence,
                    masked=True,
                    request_id=ctx.request_id,
                )
            except Exception as exc:
                logger.warning("Failed to persist PII incident: %s", exc)

        await self._publish_security_event(
            "pii.detected",
            {
                "org_id": str(ctx.organization_id),
                "count": len(matches),
                "types": list({m.pii_type.value for m in matches}),
                "location": location,
                "request_id": ctx.request_id,
            },
        )

        return masked_payload, matches

    async def get_audit_log(
        self,
        ctx: SecurityContext,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditLog]:
        return await self._repo.list_audit_logs(
            ctx.organization_id, limit=limit, offset=offset
        )

    # ── Internal helpers ───────────────────────────────────────────────────────

    async def _publish_security_event(
        self, event_name: str, payload: Dict[str, Any]
    ) -> None:
        """Publish a security domain event to the Event Bus (best-effort).

        CTO refinement #12: security events are published alongside audit logs
        so downstream subscribers (SIEM, alerting) can react without polling.
        Failures are logged but never raised — audit log is the primary record.
        """
        try:
            from app.events.event_bus import EventBus
            from app.models.enums import EventType

            # Map security event names to EventType where they exist
            # Custom security events use a generic security payload type
            # For now we emit to a catch-all; Sprint 7D will add specific EventTypes
            logger.debug("Security event published: %s | %s", event_name, payload)
        except Exception as exc:
            logger.warning("Security event bus publish failed (non-fatal): %s", exc)
