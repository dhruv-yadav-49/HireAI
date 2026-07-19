import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.lead import Lead


class LeadRepository:
    """Persistence only for Lead model. Enforces tenant boundaries strictly
    via ctx.tenant_id. No role or permission checks.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, lead: Lead) -> Lead:
        self.db.add(lead)
        await self.db.flush()
        return lead

    async def get_by_id(self, ctx: RequestContext, lead_id: uuid.UUID) -> Lead | None:
        """Finds non-deleted lead matching ID and tenant ID."""
        result = await self.db.execute(
            select(Lead).where(
                Lead.id == lead_id,
                Lead.organization_id == ctx.tenant_id,
                Lead.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        ctx: RequestContext,
        status: str | None = None,
        priority: str | None = None,
        assigned_to: uuid.UUID | None = None,
        source: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> tuple[list[Lead], int]:
        """List non-deleted leads with filters, search, pagination, and sorting."""
        # 1. Base Query
        stmt = select(Lead).where(
            Lead.organization_id == ctx.tenant_id,
            Lead.deleted_at.is_(None),
        )

        # 2. Filters
        if status is not None:
            stmt = stmt.where(Lead.status == status)
        if priority is not None:
            stmt = stmt.where(Lead.priority == priority)
        if assigned_to is not None:
            stmt = stmt.where(Lead.assigned_to == assigned_to)
        if source is not None:
            stmt = stmt.where(Lead.source == source)

        # 3. Search
        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Lead.first_name.ilike(search_pattern),
                    Lead.last_name.ilike(search_pattern),
                    Lead.company_name.ilike(search_pattern),
                    Lead.email.ilike(search_pattern),
                    Lead.phone.ilike(search_pattern),
                )
            )

        # 4. Count query
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # 5. Sorting
        sort_column = Lead.created_at
        if sort_by == "estimated_value":
            sort_column = Lead.estimated_value
        elif sort_by == "last_name":
            sort_column = Lead.last_name
        elif sort_by == "last_activity_at":
            sort_column = Lead.last_activity_at

        if sort_dir.lower() == "asc":
            stmt = stmt.order_by(sort_column.asc())
        else:
            stmt = stmt.order_by(sort_column.desc())

        # 6. Pagination
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)

        result = await self.db.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def update(self, lead: Lead) -> Lead:
        """Saves current state of lead. Calls flush to refresh DB attributes."""
        self.db.add(lead)
        await self.db.flush()
        return lead

    async def soft_delete(self, ctx: RequestContext, lead_id: uuid.UUID) -> bool:
        """Performs tenant-safe soft deletion."""
        lead = await self.get_by_id(ctx, lead_id)
        if lead is None:
            return False
        lead.deleted_at = datetime.now(timezone.utc)
        self.db.add(lead)
        await self.db.flush()
        return True

    async def get_by_id_include_deleted(self, ctx: RequestContext, lead_id: uuid.UUID) -> Lead | None:
        """Retrieves lead by ID including soft-deleted leads."""
        stmt = select(Lead).where(
            Lead.id == lead_id,
            Lead.organization_id == ctx.tenant_id,
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def restore(self, ctx: RequestContext, lead_id: uuid.UUID) -> Lead | None:
        """Restores a soft-deleted lead."""
        lead = await self.get_by_id_include_deleted(ctx, lead_id)
        if lead is None or lead.deleted_at is None:
            return None
        lead.deleted_at = None
        self.db.add(lead)
        await self.db.flush()
        return lead

    async def email_exists(
        self, ctx: RequestContext, email: str, exclude_id: uuid.UUID | None = None
    ) -> bool:
        """Case-insensitive check for active emails within the organization."""
        stmt = select(Lead).where(
            Lead.organization_id == ctx.tenant_id,
            func.lower(Lead.email) == email.lower(),
            Lead.deleted_at.is_(None),
        )
        if exclude_id is not None:
            stmt = stmt.where(Lead.id != exclude_id)
        result = await self.db.execute(stmt)
        return result.first() is not None

    async def phone_exists(
        self, ctx: RequestContext, phone: str, exclude_id: uuid.UUID | None = None
    ) -> bool:
        """Check for active duplicates of E.164 formatted phone number within the organization."""
        stmt = select(Lead).where(
            Lead.organization_id == ctx.tenant_id,
            Lead.phone == phone,
            Lead.deleted_at.is_(None),
        )
        if exclude_id is not None:
            stmt = stmt.where(Lead.id != exclude_id)
        result = await self.db.execute(stmt)
        return result.first() is not None
