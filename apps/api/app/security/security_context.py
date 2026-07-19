"""
app/security/security_context.py

Immutable SecurityContext — the single source of truth for identity and
authorization decisions throughout the security layer.

ADR-021 (CTO refinement #1): Every security decision consumes this object.
Passing individual values through functions is prohibited.
"""
import uuid
from dataclasses import dataclass, field
from typing import FrozenSet, Optional

from app.models.enums import AuthMethod


@dataclass(frozen=True)
class SecurityContext:
    """Immutable per-request security identity snapshot.

    Built once by the authentication pipeline and passed to every
    authorization, audit, and PII component. Frozen=True ensures no
    mutation after construction — same thread-safety guarantee as
    RequestContext.
    """

    # Identity
    user_id: uuid.UUID
    organization_id: uuid.UUID

    # Authorization
    roles: FrozenSet[str]
    permissions: FrozenSet[str]  # resolved resource-level permissions

    # Authentication metadata
    auth_method: AuthMethod
    api_key_id: Optional[uuid.UUID] = None   # set when auth_method == API_KEY

    # Request correlation (CTO refinement #1)
    request_id: str = ""
    correlation_id: str = ""

    # Network metadata (for audit + incident response)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    # ── Convenience helpers ────────────────────────────────────────────────────

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

    def is_api_key_auth(self) -> bool:
        return self.auth_method == AuthMethod.API_KEY

    def is_human_auth(self) -> bool:
        return self.auth_method in (
            AuthMethod.JWT, AuthMethod.OAUTH, AuthMethod.OIDC, AuthMethod.SAML
        )

    def cache_key(self) -> str:
        """Stable string key for the authorization decision cache."""
        return f"{self.user_id}:{self.organization_id}:{self.auth_method.value}"


def build_security_context(
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    roles: set[str],
    permissions: set[str],
    auth_method: AuthMethod,
    request_id: str = "",
    correlation_id: str = "",
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    api_key_id: Optional[uuid.UUID] = None,
) -> SecurityContext:
    """Factory function — converts mutable sets to frozensets before freezing."""
    return SecurityContext(
        user_id=user_id,
        organization_id=organization_id,
        roles=frozenset(roles),
        permissions=frozenset(permissions),
        auth_method=auth_method,
        api_key_id=api_key_id,
        request_id=request_id,
        correlation_id=correlation_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
