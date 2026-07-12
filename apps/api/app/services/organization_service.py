"""
app/services/organization_service.py

OrganizationService — all organization business logic.

Key design decisions (ADR-002, ADR-004):
- Membership is managed via OrganizationMember, never via user.org_id
- Organization Settings is a singleton: GET/PATCH only, no POST
- Org switch runs inside an explicit transaction (audit log + session update atomic)
- business_hours uses day-level merge (see _merge_business_hours)
- Role is never read from JWT — always from RequestContext.membership.role
"""

import uuid

from slugify import slugify
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    InsufficientRoleError,
    NoActiveOrganizationError,
    OrganizationNotFoundException,
    OrganizationSuspendedException,
)
from app.models.enums import MemberStatus, OrganizationRole, OrganizationStatus
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.organization_settings import OrganizationSettings
from app.models.user import User
from app.models.user_session import UserSession
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_session_repository import UserSessionRepository
from app.schemas.organization import (
    OrganizationCreateRequest,
    OrganizationMeResponse,
    OrganizationSettingsUpdateRequest,
    OrganizationSwitchRequest,
    OrganizationUpdateRequest,
)

# Roles that can update organization settings
_CAN_MANAGE_SETTINGS = {OrganizationRole.OWNER, OrganizationRole.ADMIN}

_MAX_SLUG_ATTEMPTS = 20

# Audit event types
EVENT_ORG_SWITCH = "org_switch"


class OrganizationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.org_repo = OrganizationRepository(db)
        self.session_repo = UserSessionRepository(db)

    # ── Create Organization ────────────────────────────────────────────────────

    async def create_organization(
        self, user: User, data: OrganizationCreateRequest, session: UserSession | None = None
    ) -> Organization:
        slug = await self._generate_unique_slug(data.name)

        organization = Organization(
            name=data.name,
            slug=slug,
            industry=data.industry,
            company_size=data.company_size,
            country=data.country,
            timezone=data.timezone,
            owner_id=user.id,
        )
        await self.org_repo.create(organization)

        # Owner membership must always exist alongside organizations.owner_id.
        # Both are written in the same transaction — they must never go out of sync.
        owner_membership = OrganizationMember(
            organization_id=organization.id,
            user_id=user.id,
            role=OrganizationRole.OWNER,
            status=MemberStatus.ACTIVE,
        )
        await self.org_repo.add_member(owner_membership)

        # Initialize lead sequence generator for this new tenant
        from app.models.organization_sequence import OrganizationSequence
        seq = OrganizationSequence(organization_id=organization.id, next_lead_number=1001)
        self.db.add(seq)

        if session is not None:
            session.active_organization_id = organization.id
            self.db.add(session)

        await self.db.commit()
        return organization

    # ── Get Current Organization ───────────────────────────────────────────────

    async def get_current_organization(self, user: User) -> OrganizationMeResponse:
        """Sprint 2A stand-in. In Sprint 2C+, use get_request_context() instead."""
        membership = await self.org_repo.get_first_membership_for_user(user.id)
        if membership is None:
            raise NoActiveOrganizationError()

        organization = await self.org_repo.get_by_id(membership.organization_id)
        if organization is None:
            raise OrganizationNotFoundException()

        return OrganizationMeResponse(
            id=organization.id,
            name=organization.name,
            slug=organization.slug,
            industry=organization.industry,
            company_size=organization.company_size,
            country=organization.country,
            timezone=organization.timezone,
            logo_url=organization.logo_url,
            status=organization.status,
            role=membership.role,
        )

    # ── Update Organization ────────────────────────────────────────────────────

    async def update_organization(
        self, user: User, organization_id: uuid.UUID, data: OrganizationUpdateRequest
    ) -> Organization:
        organization = await self.org_repo.get_by_id(organization_id)
        if organization is None:
            raise OrganizationNotFoundException()

        membership = await self.org_repo.get_membership(organization_id, user.id)
        if membership is None:
            raise OrganizationNotFoundException()
        if membership.role not in _CAN_MANAGE_SETTINGS:
            raise InsufficientRoleError()

        updates = data.model_dump(exclude_unset=True)
        await self.org_repo.update(organization, **updates)
        await self.db.commit()
        return organization

    # ── Switch Organization (Sprint 2C) ───────────────────────────────────────

    async def switch_organization(
        self,
        ctx: "RequestContext",  # noqa: F821 — resolved at runtime
        data: OrganizationSwitchRequest,
    ) -> OrganizationMeResponse:
        """
        Switch the session's active organization.

        Business rules:
        1. Target org must exist and not be soft-deleted
        2. Target org must be ACTIVE or TRIAL (not SUSPENDED/EXPIRED)
        3. User must have an ACTIVE membership in the target org
        4. Session update + audit log run in a single explicit transaction
        """
        from app.core.context import RequestContext

        # Validate target org
        org = await self.org_repo.get_by_id(data.organization_id)
        if org is None:
            raise OrganizationNotFoundException()

        if org.status in (OrganizationStatus.SUSPENDED, OrganizationStatus.EXPIRED):
            raise OrganizationSuspendedException()

        membership = await self.org_repo.get_active_membership(
            data.organization_id, ctx.user.id
        )
        if membership is None:
            raise InsufficientRoleError(
                "You are not an active member of this organization."
            )

        previous_org_id = ctx.session.active_organization_id

        # Explicit transaction: session update + audit log are atomic
        async with self.db.begin_nested():
            await self.session_repo.update_active_organization(
                ctx.session, data.organization_id
            )
            await self._log_org_switch(
                user=ctx.user,
                session_id=ctx.session.id,
                from_org_id=previous_org_id,
                to_org_id=data.organization_id,
                ip_address=ctx.session.ip_address,
            )
        await self.db.commit()

        return OrganizationMeResponse(
            id=org.id,
            name=org.name,
            slug=org.slug,
            industry=org.industry,
            company_size=org.company_size,
            country=org.country,
            timezone=org.timezone,
            logo_url=org.logo_url,
            status=org.status,
            role=membership.role,
        )

    # ── Organization Settings (Sprint 2C) ──────────────────────────────────────

    async def get_or_create_settings(
        self, ctx: "RequestContext"
    ) -> OrganizationSettings:
        """Idempotent — creates default settings row on first access.
        Any ACTIVE member can read settings.
        """
        settings_row = await self.org_repo.get_settings(ctx.tenant_id)
        if settings_row is None:
            settings_row = await self.org_repo.create_settings(ctx.tenant_id)
            await self.db.commit()
        return settings_row

    async def update_settings(
        self,
        ctx: "RequestContext",
        data: OrganizationSettingsUpdateRequest,
    ) -> OrganizationSettings:
        """Update organization settings. OWNER/ADMIN only."""
        if not ctx.can_manage_settings():
            raise InsufficientRoleError(
                "Only OWNER or ADMIN can update organization settings."
            )

        settings_row = await self.org_repo.get_settings(ctx.tenant_id)
        if settings_row is None:
            settings_row = await self.org_repo.create_settings(ctx.tenant_id)

        updates = data.model_dump(exclude_unset=True)

        # Day-level merge for business_hours (see ADR-004)
        if "business_hours" in updates and updates["business_hours"] is not None:
            patch_hours: dict = {
                day: schedule.model_dump()
                for day, schedule in (data.business_hours or {}).items()
            }
            updates["business_hours"] = self._merge_business_hours(
                settings_row.business_hours, patch_hours
            )

        await self.org_repo.update_settings(settings_row, **updates)
        await self.db.commit()
        return settings_row

    # ── Private Helpers ────────────────────────────────────────────────────────

    async def _generate_unique_slug(self, name: str) -> str:
        base_slug = slugify(name)
        candidate = base_slug
        for attempt in range(2, _MAX_SLUG_ATTEMPTS + 1):
            if not await self.org_repo.slug_exists(candidate):
                return candidate
            candidate = f"{base_slug}-{attempt}"
        return f"{base_slug}-{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _merge_business_hours(
        current: dict | None,
        patch: dict,
    ) -> dict:
        """Day-level merge — entire day object is replaced for any day in patch.
        Days not present in patch are untouched.

        Example:
            current = {"monday": {"enabled": True, "start": "09:00", "end": "17:00"}}
            patch   = {"monday": {"enabled": True, "end": "19:00"}}
            result  = {"monday": {"enabled": True, "end": "19:00"}}  # start is gone
        Clients must always send a complete day object.
        """
        base = dict(current or {})
        base.update(patch)
        return base

    async def _log_org_switch(
        self,
        user: User,
        session_id: uuid.UUID,
        from_org_id: uuid.UUID | None,
        to_org_id: uuid.UUID,
        ip_address: str | None,
    ) -> None:
        """Write an audit log entry for org_switch. Runs inside the caller's transaction."""
        from app.models.login_audit_log import LoginAuditLog

        log = LoginAuditLog(
            email=user.email,
            ip_address=ip_address,
            event_type=EVENT_ORG_SWITCH,
            session_id=session_id,
            event_metadata={
                "from_org_id": str(from_org_id) if from_org_id else None,
                "to_org_id": str(to_org_id),
            },
        )
        self.db.add(log)
        await self.db.flush()
