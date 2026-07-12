"""
app/core/context.py

RequestContext — the single source of truth for who is making a request,
under which tenant, with what role.

Architecture decisions (ADR-003):
- frozen=True: immutable per request, thread-safe
- Built once per request, cached in request.state.ctx
- role is always resolved at runtime from membership.role — NEVER from JWT
- permissions is None until the permission engine lands (not an empty frozenset)
- tenant_id is a convenience property: ctx.tenant_id == ctx.organization.id
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    InsufficientRoleError,
    NoActiveOrganizationError,
    OrganizationNotFoundException,
    OrganizationSuspendedException,
)
from app.models.enums import OrganizationRole, OrganizationStatus

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.organization_member import OrganizationMember
    from app.models.user import User
    from app.models.user_session import UserSession


@dataclass(frozen=True)
class RequestContext:
    request_id: str
    request_start_time: datetime          # UTC — for latency/audit logging
    session: "UserSession"
    user: "User"
    organization: "Organization"
    membership: "OrganizationMember"
    role: "OrganizationRole"              # alias: membership.role (always fresh, never from JWT)
    permissions: Optional[frozenset[str]] = None  # None until permission engine lands

    # ── Convenience shortcut ───────────────────────────────────────────────────
    @property
    def tenant_id(self) -> uuid.UUID:
        """Use ctx.tenant_id instead of ctx.organization.id throughout the codebase."""
        return self.organization.id

    # ── Role helper methods ────────────────────────────────────────────────────
    def is_owner(self) -> bool:
        return self.role == OrganizationRole.OWNER

    def is_admin(self) -> bool:
        """True for OWNER and ADMIN — the two roles that can manage settings."""
        return self.role in (OrganizationRole.OWNER, OrganizationRole.ADMIN)

    def is_sales(self) -> bool:
        return self.role == OrganizationRole.SALES

    def can_manage_settings(self) -> bool:
        """OWNER or ADMIN can update organization settings."""
        return self.is_admin()

    # Future: def can(self, permission: str) -> bool: ...


async def build_request_context(
    request: Request,
    user: "User",
    session: "UserSession",
    db: AsyncSession,
) -> RequestContext:
    """
    Pure async helper — not a class or service.
    Builds RequestContext from the current session and caches it in
    request.state.ctx so subsequent DI dependencies in the same request
    pay zero extra DB queries.

    Raises:
        NoActiveOrganizationError (404)  — session has no active_organization_id
                                           → frontend should open org selector
        OrganizationNotFoundException (404) — org deleted or not found
        OrganizationSuspendedException (403) — org is SUSPENDED or EXPIRED
        InsufficientRoleError (403)      — user's membership is not ACTIVE
    """
    # ── Cache hit — zero extra DB queries ────────────────────────────────────
    cached = getattr(request.state, "ctx", None)
    if cached is not None:
        return cached  # type: ignore[return-value]

    # ── Lazy imports to avoid circular deps ──────────────────────────────────
    from app.repositories.organization_repository import OrganizationRepository

    # ── Resolve organization from session ────────────────────────────────────
    if not session.active_organization_id:
        raise NoActiveOrganizationError()

    org_repo = OrganizationRepository(db)
    org = await org_repo.get_by_id(session.active_organization_id)

    if org is None or getattr(org, "deleted_at", None) is not None:
        raise OrganizationNotFoundException()

    if org.status in (OrganizationStatus.SUSPENDED, OrganizationStatus.EXPIRED):
        raise OrganizationSuspendedException()

    membership = await org_repo.get_active_membership(org.id, user.id)
    if membership is None:
        raise InsufficientRoleError("Your membership in this organization is not active.")

    # ── X-Request-ID: prefer header, fall back to generated UUID ─────────────
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

    ctx = RequestContext(
        request_id=request_id,
        request_start_time=datetime.now(timezone.utc),
        session=session,
        user=user,
        organization=org,
        membership=membership,
        role=membership.role,
    )

    # ── Store in request state for reuse ─────────────────────────────────────
    request.state.ctx = ctx
    return ctx
