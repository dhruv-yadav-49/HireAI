import uuid

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.lead_tag import LeadTag, LeadTagAssignment


class LeadTagRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_tag(self, tag: LeadTag) -> LeadTag:
        self.db.add(tag)
        await self.db.flush()
        return tag

    async def get_tag_by_name(self, ctx: RequestContext, name: str) -> LeadTag | None:
        result = await self.db.execute(
            select(LeadTag).where(
                LeadTag.organization_id == ctx.tenant_id,
                LeadTag.name == name,
            )
        )
        return result.scalar_one_or_none()

    async def get_tag_by_id(self, ctx: RequestContext, tag_id: uuid.UUID) -> LeadTag | None:
        result = await self.db.execute(
            select(LeadTag).where(
                LeadTag.organization_id == ctx.tenant_id,
                LeadTag.id == tag_id,
            )
        )
        return result.scalar_one_or_none()

    async def assign_tag(self, lead_id: uuid.UUID, tag_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Idempotently assign a tag to a lead. Returns True if newly assigned."""
        stmt = select(LeadTagAssignment).where(
            LeadTagAssignment.lead_id == lead_id,
            LeadTagAssignment.tag_id == tag_id,
        )
        res = await self.db.execute(stmt)
        if res.scalar_one_or_none() is not None:
            return False  # Already assigned

        assignment = LeadTagAssignment(
            lead_id=lead_id,
            tag_id=tag_id,
            created_by=user_id,
        )
        self.db.add(assignment)
        await self.db.flush()
        return True

    async def remove_tag(self, lead_id: uuid.UUID, tag_id: uuid.UUID) -> bool:
        """Remove a tag assignment. Returns True if removed."""
        stmt = delete(LeadTagAssignment).where(
            LeadTagAssignment.lead_id == lead_id,
            LeadTagAssignment.tag_id == tag_id,
        )
        res = await self.db.execute(stmt)
        await self.db.flush()
        return (res.rowcount or 0) > 0

    async def get_tags_for_lead(self, ctx: RequestContext, lead_id: uuid.UUID) -> list[LeadTag]:
        """Fetch all tags currently assigned to a lead, validating tenant safety."""
        stmt = (
            select(LeadTag)
            .join(LeadTagAssignment, LeadTag.id == LeadTagAssignment.tag_id)
            .where(
                LeadTagAssignment.lead_id == lead_id,
                LeadTag.organization_id == ctx.tenant_id,
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
