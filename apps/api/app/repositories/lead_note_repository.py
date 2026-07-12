import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.lead import Lead
from app.models.lead_note import LeadNote


class LeadNoteRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, note: LeadNote) -> LeadNote:
        self.db.add(note)
        await self.db.flush()
        return note

    async def get_by_id(self, ctx: RequestContext, note_id: uuid.UUID) -> LeadNote | None:
        """Fetch lead note, asserting it belongs to a lead of the active tenant."""
        stmt = (
            select(LeadNote)
            .join(Lead, LeadNote.lead_id == Lead.id)
            .where(
                LeadNote.id == note_id,
                Lead.organization_id == ctx.tenant_id,
                LeadNote.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_lead(self, ctx: RequestContext, lead_id: uuid.UUID) -> list[LeadNote]:
        """Fetch all non-deleted notes for a specific lead within the tenant, ordered oldest to newest."""
        stmt = (
            select(LeadNote)
            .join(Lead, LeadNote.lead_id == Lead.id)
            .where(
                LeadNote.lead_id == lead_id,
                Lead.organization_id == ctx.tenant_id,
                LeadNote.deleted_at.is_(None),
            )
            .order_by(LeadNote.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def soft_delete(self, ctx: RequestContext, note_id: uuid.UUID) -> bool:
        note = await self.get_by_id(ctx, note_id)
        if note is None:
            return False
        note.deleted_at = datetime.now(timezone.utc)
        self.db.add(note)
        await self.db.flush()
        return True
