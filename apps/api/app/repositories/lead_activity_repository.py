import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.lead import Lead
from app.models.lead_activity import LeadActivity


class LeadActivityRepository:
    """Timeline activities repository. Immutable (append-only timeline rule).
    No update or delete operations are exposed.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_activity(self, activity: LeadActivity) -> LeadActivity:
        self.db.add(activity)
        await self.db.flush()
        return activity

    async def list_for_lead(self, ctx: RequestContext, lead_id: uuid.UUID) -> list[LeadActivity]:
        """Fetch all activities for a lead within the tenant, ordered newest-first."""
        stmt = (
            select(LeadActivity)
            .join(Lead, LeadActivity.lead_id == Lead.id)
            .where(
                LeadActivity.lead_id == lead_id,
                Lead.organization_id == ctx.tenant_id,
            )
            .order_by(LeadActivity.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
