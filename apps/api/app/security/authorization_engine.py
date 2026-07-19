"""
app/security/authorization_engine.py

Orchestrates the full authorization chain:
    Identity → RBAC → ABAC → TenantPolicy → Decision

CTO refinement #8: In-memory decision cache keyed by
(SecurityContext.cache_key, resource_type, action) with a 60-second TTL.
This prevents redundant RBAC + ABAC evaluations on the hot path.

ADR-021: Zero Trust — every request is authorized independently.
ADR-021: Security by Composition — authorization wraps business logic.
"""
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.models.enums import OrganizationRole
from app.security.rbac_engine import RBACEngine
from app.security.abac_engine import ABACEngine, ABACEffect, ABACPolicy
from app.security.security_context import SecurityContext


@dataclass(frozen=True)
class AuthDecision:
    """Result of an authorization check."""
    allowed: bool
    reason: str
    policy_name: Optional[str] = None
    cached: bool = False


# ── In-memory authorization cache (CTO refinement #8) ─────────────────────────

_CACHE_TTL_SECONDS = 60

class _DecisionCache:
    """Simple TTL cache: (context_key, resource_type, action) → (decision, expires_at)."""

    def __init__(self) -> None:
        self._store: Dict[str, tuple[AuthDecision, float]] = {}

    def _key(self, ctx_key: str, resource_type: str, action: str) -> str:
        return f"{ctx_key}|{resource_type}|{action}"

    def get(self, ctx_key: str, resource_type: str, action: str) -> Optional[AuthDecision]:
        k = self._key(ctx_key, resource_type, action)
        entry = self._store.get(k)
        if entry is None:
            return None
        decision, expires_at = entry
        if time.monotonic() > expires_at:
            del self._store[k]
            return None
        return decision

    def set(self, ctx_key: str, resource_type: str, action: str, decision: AuthDecision) -> None:
        k = self._key(ctx_key, resource_type, action)
        self._store[k] = (decision, time.monotonic() + _CACHE_TTL_SECONDS)

    def invalidate(self, ctx_key: str) -> None:
        """Invalidate all cached decisions for a given context (e.g. on role change)."""
        prefix = f"{ctx_key}|"
        to_delete = [k for k in self._store if k.startswith(prefix)]
        for k in to_delete:
            del self._store[k]

    def clear(self) -> None:
        self._store.clear()


_cache = _DecisionCache()


class AuthorizationEngine:
    """Stateless authorization orchestrator.

    Chain:
      1. RBAC check (role → resource-level permission)
      2. ABAC check (attribute policies)
      3. Tenant policy check (org-level overrides)

    Short-circuits on first DENY. ALLOW requires passing all stages.
    """

    @staticmethod
    def authorize(
        ctx: SecurityContext,
        resource_type: str,
        action: str,
        resource_attrs: Optional[Dict[str, Any]] = None,
        abac_policies: Optional[List[ABACPolicy]] = None,
        tenant_allowed: bool = True,
    ) -> AuthDecision:
        """Evaluate authorization for a given (SecurityContext, resource, action).

        Args:
            ctx: Immutable SecurityContext built by the authentication pipeline.
            resource_type: e.g. "Lead", "APIKey", "Workflow"
            action: e.g. "read", "create", "delete"
            resource_attrs: attribute dict for ABAC evaluation (optional)
            abac_policies: list of ABAC policies to evaluate (optional)
            tenant_allowed: result of tenant policy check (pre-computed)

        Returns:
            AuthDecision with allowed=True/False, reason, and cache status.
        """
        cache_key = ctx.cache_key()

        # ── Cache hit ──────────────────────────────────────────────────────────
        cached = _cache.get(cache_key, resource_type, action)
        if cached is not None:
            return AuthDecision(
                allowed=cached.allowed,
                reason=cached.reason,
                policy_name=cached.policy_name,
                cached=True,
            )

        # ── Stage 1: RBAC ──────────────────────────────────────────────────────
        # Determine role from permissions set on SecurityContext
        # We check the permission strings directly (e.g. "Lead:delete")
        permission_str = f"{resource_type}:{action}"
        rbac_allowed = (
            permission_str in ctx.permissions
            or f"{resource_type}:*" in ctx.permissions
        )

        if not rbac_allowed:
            decision = AuthDecision(
                allowed=False,
                reason=f"RBAC: role lacks '{permission_str}' permission",
                policy_name="rbac",
            )
            _cache.set(cache_key, resource_type, action, decision)
            return decision

        # ── Stage 2: ABAC ──────────────────────────────────────────────────────
        if abac_policies:
            attrs = resource_attrs or {}
            effect = ABACEngine.evaluate_all(abac_policies, attrs)
            if effect == ABACEffect.DENY:
                decision = AuthDecision(
                    allowed=False,
                    reason="ABAC: attribute policy denied the request",
                    policy_name="abac",
                )
                _cache.set(cache_key, resource_type, action, decision)
                return decision

        # ── Stage 3: Tenant Policy ─────────────────────────────────────────────
        if not tenant_allowed:
            decision = AuthDecision(
                allowed=False,
                reason="Tenant security policy denied the request",
                policy_name="tenant_policy",
            )
            _cache.set(cache_key, resource_type, action, decision)
            return decision

        # ── ALLOW ──────────────────────────────────────────────────────────────
        decision = AuthDecision(
            allowed=True,
            reason=f"Authorized: RBAC+ABAC+TenantPolicy all passed for '{permission_str}'",
        )
        _cache.set(cache_key, resource_type, action, decision)
        return decision

    @staticmethod
    def invalidate_cache(ctx_key: str) -> None:
        """Invalidate cached decisions for a security context (e.g. after role change)."""
        _cache.invalidate(ctx_key)

    @staticmethod
    def clear_cache() -> None:
        """Clear entire authorization cache. Use in tests."""
        _cache.clear()
