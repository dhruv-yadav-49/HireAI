"""
app/repositories/security_repository.py

Data access layer for all Sprint 7C security models.
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import APIKey
from app.models.audit_log import AuditLog
from app.models.enums import APIKeyStatus, AuditAction, PIIType, SecretType
from app.models.pii_incident import PIIIncident
from app.models.secret_reference import SecretReference
from app.models.security_policy import SecurityPolicy


class SecurityRepository:
    """Repository for security domain models."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── API Keys ───────────────────────────────────────────────────────────────

    async def get_api_key_by_prefix(self, prefix: str) -> Optional[APIKey]:
        stmt = select(APIKey).where(
            APIKey.prefix == prefix,
            APIKey.status == APIKeyStatus.ACTIVE,
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_api_key_by_id(self, key_id: uuid.UUID) -> Optional[APIKey]:
        stmt = select(APIKey).where(APIKey.id == key_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_api_key(
        self,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        name: str,
        hashed_key: str,
        prefix: str,
        scopes: List[str],
        expires_at: Optional[datetime] = None,
        created_from: Optional[str] = None,
    ) -> APIKey:
        key = APIKey(
            id=uuid.uuid4(),
            organization_id=organization_id,
            user_id=user_id,
            name=name,
            hashed_key=hashed_key,
            prefix=prefix,
            scopes_json=scopes,
            expires_at=expires_at,
            status=APIKeyStatus.ACTIVE,
            created_from=created_from,
            created_at=datetime.now(timezone.utc),
        )
        self._db.add(key)
        await self._db.flush()
        return key

    async def revoke_api_key(self, key_id: uuid.UUID) -> None:
        stmt = (
            update(APIKey)
            .where(APIKey.id == key_id)
            .values(status=APIKeyStatus.REVOKED)
        )
        await self._db.execute(stmt)
        await self._db.flush()

    async def list_api_keys(
        self, org_id: uuid.UUID, include_revoked: bool = False
    ) -> List[APIKey]:
        stmt = select(APIKey).where(APIKey.organization_id == org_id)
        if not include_revoked:
            stmt = stmt.where(APIKey.status == APIKeyStatus.ACTIVE)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def touch_api_key(
        self,
        key_id: uuid.UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Update last_used_at, last_ip, last_user_agent."""
        values: dict = {"last_used_at": datetime.now(timezone.utc)}
        if ip_address is not None:
            values["last_ip"] = ip_address
        if user_agent is not None:
            values["last_user_agent"] = user_agent[:500]
        stmt = update(APIKey).where(APIKey.id == key_id).values(**values)
        await self._db.execute(stmt)

    # ── Security Policies ──────────────────────────────────────────────────────

    async def get_security_policy(
        self, org_id: uuid.UUID
    ) -> Optional[SecurityPolicy]:
        stmt = select(SecurityPolicy).where(
            SecurityPolicy.organization_id == org_id,
            SecurityPolicy.enabled.is_(True),
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_default_policy(self) -> Optional[SecurityPolicy]:
        stmt = select(SecurityPolicy).where(
            SecurityPolicy.organization_id.is_(None),
            SecurityPolicy.enabled.is_(True),
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_security_policy(
        self,
        org_id: Optional[uuid.UUID],
        policy_name: str,
        rules: dict,
    ) -> SecurityPolicy:
        existing = None
        if org_id:
            existing = await self.get_security_policy(org_id)
        else:
            existing = await self.get_default_policy()

        now = datetime.now(timezone.utc)
        if existing:
            existing.rules_json = rules
            existing.policy_name = policy_name
            existing.updated_at = now
            await self._db.flush()
            return existing

        policy = SecurityPolicy(
            id=uuid.uuid4(),
            organization_id=org_id,
            policy_name=policy_name,
            rules_json=rules,
            enabled=True,
            created_at=now,
        )
        self._db.add(policy)
        await self._db.flush()
        return policy

    async def list_security_policies(
        self, org_id: uuid.UUID
    ) -> List[SecurityPolicy]:
        stmt = select(SecurityPolicy).where(
            SecurityPolicy.organization_id == org_id
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    # ── Audit Logs ─────────────────────────────────────────────────────────────

    async def list_audit_logs(
        self,
        org_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.organization_id == org_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    # ── PII Incidents ──────────────────────────────────────────────────────────

    async def create_pii_incident(
        self,
        org_id: uuid.UUID,
        pii_type: PIIType,
        location: str,
        severity: float = 0.8,
        confidence: float = 0.8,
        masked: bool = False,
        request_id: Optional[str] = None,
    ) -> PIIIncident:
        incident = PIIIncident(
            id=uuid.uuid4(),
            organization_id=org_id,
            pii_type=pii_type,
            location=location,
            severity=severity,
            confidence=confidence,
            masked=masked,
            request_id=request_id,
            created_at=datetime.now(timezone.utc),
        )
        self._db.add(incident)
        await self._db.flush()
        return incident

    async def list_pii_incidents(
        self,
        org_id: uuid.UUID,
        limit: int = 100,
    ) -> List[PIIIncident]:
        stmt = (
            select(PIIIncident)
            .where(PIIIncident.organization_id == org_id)
            .order_by(PIIIncident.created_at.desc())
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    # ── Secret References ──────────────────────────────────────────────────────

    async def create_secret_reference(
        self,
        org_id: uuid.UUID,
        secret_name: str,
        secret_type: SecretType,
        provider: str = "env",
        rotation_period_days: Optional[int] = None,
    ) -> SecretReference:
        ref = SecretReference(
            id=uuid.uuid4(),
            organization_id=org_id,
            secret_name=secret_name,
            secret_type=secret_type,
            provider=provider,
            rotation_period_days=rotation_period_days,
            created_at=datetime.now(timezone.utc),
        )
        self._db.add(ref)
        await self._db.flush()
        return ref

    async def list_secret_references(
        self, org_id: uuid.UUID
    ) -> List[SecretReference]:
        stmt = select(SecretReference).where(
            SecretReference.organization_id == org_id
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
