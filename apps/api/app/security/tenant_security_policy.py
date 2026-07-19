"""
app/security/tenant_security_policy.py

Per-organization security policy with default→override inheritance.

CTO refinement #10: A global default policy (org_id=NULL in DB) is inherited
by all organizations. Organization-specific rules override individual fields
of the default — not the entire policy — so adding a new default setting is
automatically inherited by all tenants that haven't overridden it.

ADR-021: Tenant Isolation — security policies are enforced independently
per organization.
"""
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security_policy import SecurityPolicy

logger = logging.getLogger(__name__)


@dataclass
class TenantSecurityPolicy:
    """Resolved security policy for a given organization.

    This is the merged result of: DEFAULT_POLICY ← org override.
    Individual fields from the org override replace defaults; unset fields
    fall through to the default.
    """
    # Authentication
    allowed_auth_methods: List[str] = field(
        default_factory=lambda: ["JWT", "API_KEY"]
    )

    # Rate limiting (requests per minute)
    rate_limit_rpm: int = 1000

    # AI model allowlist (empty = all allowed)
    allowed_models: List[str] = field(default_factory=list)

    # PII enforcement: if True, PII scan runs on all payloads
    pii_enforcement: bool = True

    # MFA requirement (future enforcement hook)
    require_mfa: bool = False

    # IP allowlist (future enforcement hook; empty = all IPs allowed)
    ip_allowlist: List[str] = field(default_factory=list)

    # Maximum API key scopes allowed for this org
    max_api_key_scopes: int = 10


# Global default — used when no org-level policy exists
DEFAULT_POLICY = TenantSecurityPolicy()


def _merge(base: TenantSecurityPolicy, overrides: Dict[str, Any]) -> TenantSecurityPolicy:
    """Merge org overrides onto the base policy (field-level inheritance).

    Only keys present in the overrides dict replace the corresponding field.
    Missing keys keep the base value.
    """
    merged = TenantSecurityPolicy(
        allowed_auth_methods=overrides.get(
            "allowed_auth_methods", base.allowed_auth_methods
        ),
        rate_limit_rpm=overrides.get("rate_limit_rpm", base.rate_limit_rpm),
        allowed_models=overrides.get("allowed_models", base.allowed_models),
        pii_enforcement=overrides.get("pii_enforcement", base.pii_enforcement),
        require_mfa=overrides.get("require_mfa", base.require_mfa),
        ip_allowlist=overrides.get("ip_allowlist", base.ip_allowlist),
        max_api_key_scopes=overrides.get(
            "max_api_key_scopes", base.max_api_key_scopes
        ),
    )
    return merged


class TenantPolicyEngine:
    """Loads and evaluates tenant security policies with inheritance.

    Resolution order:
        1. Load global default policy (org_id IS NULL)
        2. Load org-specific policy (org_id = requested org)
        3. Merge: org overrides win field-by-field
    """

    @staticmethod
    async def load(db: AsyncSession, org_id: uuid.UUID) -> TenantSecurityPolicy:
        """Load the effective policy for an organization.

        Falls back to DEFAULT_POLICY if no DB records exist.
        """
        try:
            # Load global default
            default_stmt = select(SecurityPolicy).where(
                SecurityPolicy.organization_id.is_(None),
                SecurityPolicy.enabled.is_(True),
            ).limit(1)
            result = await db.execute(default_stmt)
            default_row = result.scalar_one_or_none()

            base_policy = DEFAULT_POLICY
            if default_row and default_row.rules_json:
                base_policy = _merge(DEFAULT_POLICY, default_row.rules_json)

            # Load org-specific override
            org_stmt = select(SecurityPolicy).where(
                SecurityPolicy.organization_id == org_id,
                SecurityPolicy.enabled.is_(True),
            ).limit(1)
            result = await db.execute(org_stmt)
            org_row = result.scalar_one_or_none()

            if org_row and org_row.rules_json:
                return _merge(base_policy, org_row.rules_json)

            return base_policy

        except Exception as exc:
            logger.warning(
                "Failed to load tenant security policy for org %s: %s. "
                "Falling back to default.",
                org_id,
                exc,
            )
            return DEFAULT_POLICY

    @staticmethod
    def is_auth_method_allowed(
        policy: TenantSecurityPolicy, method: str
    ) -> bool:
        """Check whether an auth method is permitted by the policy."""
        return method in policy.allowed_auth_methods

    @staticmethod
    def is_model_allowed(
        policy: TenantSecurityPolicy, model_id: str
    ) -> bool:
        """Check whether a model is on the org's allowlist.

        An empty allowlist means all models are permitted.
        """
        if not policy.allowed_models:
            return True
        return model_id in policy.allowed_models

    @staticmethod
    def get_rate_limit(policy: TenantSecurityPolicy) -> int:
        """Return the org's configured rate limit (requests per minute)."""
        return policy.rate_limit_rpm

    @staticmethod
    def requires_pii_scan(policy: TenantSecurityPolicy) -> bool:
        return policy.pii_enforcement
