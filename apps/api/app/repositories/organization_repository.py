import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.organization_settings import OrganizationSettings
from app.models.enums import MemberStatus, OrganizationStatus


class OrganizationRepository:
    """Persistence only. No slug generation, no transaction orchestration,
    no business logic — that all lives in OrganizationService.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Organization CRUD ──────────────────────────────────────────────────────

    async def create(self, organization: Organization) -> Organization:
        self.db.add(organization)
        await self.db.flush()
        return organization

    async def get_by_id(self, organization_id: uuid.UUID) -> Organization | None:
        result = await self.db.execute(
            select(Organization).where(
                Organization.id == organization_id,
                Organization.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Organization | None:
        result = await self.db.execute(
            select(Organization).where(
                Organization.slug == slug,
                Organization.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def slug_exists(self, slug: str) -> bool:
        return await self.get_by_slug(slug) is not None

    async def update(self, organization: Organization, **fields) -> Organization:
        for key, value in fields.items():
            setattr(organization, key, value)
        await self.db.flush()
        return organization

    # ── Membership ─────────────────────────────────────────────────────────────

    async def add_member(self, member: OrganizationMember) -> OrganizationMember:
        self.db.add(member)
        await self.db.flush()
        return member

    async def get_membership(
        self, organization_id: uuid.UUID, user_id: uuid.UUID
    ) -> OrganizationMember | None:
        """Returns membership regardless of status. Used internally."""
        result = await self.db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_active_membership(
        self, organization_id: uuid.UUID, user_id: uuid.UUID
    ) -> OrganizationMember | None:
        """Returns membership only if status == ACTIVE. Used by request context
        and org switch — ensures suspended members cannot operate."""
        result = await self.db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
                OrganizationMember.status == MemberStatus.ACTIVE,
            )
        )
        return result.scalar_one_or_none()

    async def get_user_active_memberships(
        self, user_id: uuid.UUID
    ) -> list[OrganizationMember]:
        """All ACTIVE memberships for a user — used for org switcher list."""
        result = await self.db.execute(
            select(OrganizationMember).where(
                OrganizationMember.user_id == user_id,
                OrganizationMember.status == MemberStatus.ACTIVE,
            )
        )
        return list(result.scalars().all())

    async def get_first_membership_for_user(
        self, user_id: uuid.UUID
    ) -> OrganizationMember | None:
        """Sprint 2A stand-in — returns the user's first membership.
        Superseded by get_user_active_memberships in Sprint 2C.
        """
        result = await self.db.execute(
            select(OrganizationMember).where(OrganizationMember.user_id == user_id)
        )
        return result.scalars().first()

    # ── Organization Settings ──────────────────────────────────────────────────

    async def get_settings(
        self, organization_id: uuid.UUID
    ) -> OrganizationSettings | None:
        result = await self.db.execute(
            select(OrganizationSettings).where(
                OrganizationSettings.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def create_settings(
        self, organization_id: uuid.UUID
    ) -> OrganizationSettings:
        """Create default settings row. Idempotent — call get_settings first."""
        settings_row = OrganizationSettings(organization_id=organization_id)
        self.db.add(settings_row)
        await self.db.flush()
        return settings_row

    async def update_settings(
        self, settings_row: OrganizationSettings, **fields
    ) -> OrganizationSettings:
        for key, value in fields.items():
            setattr(settings_row, key, value)
        await self.db.flush()
        return settings_row
