import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.events import DomainEvent, get_event_publisher
from app.core.exceptions import (
    ConcurrentUpdateException,
    InsufficientRoleError,
    LeadNotFoundException,
    ValidationException,
)
from app.models.enums import (
    ActorType,
    CreatedSource,
    LeadActivityType,
    LeadPriority,
    LeadSource,
    LeadStatus,
)
from app.models.lead import Lead
from app.models.lead_activity import LeadActivity
from app.models.lead_note import LeadNote
from app.models.lead_tag import LeadTag
from app.models.organization_sequence import OrganizationSequence
from app.repositories.lead_repository import LeadRepository
from app.repositories.lead_note_repository import LeadNoteRepository
from app.repositories.lead_tag_repository import LeadTagRepository
from app.repositories.lead_activity_repository import LeadActivityRepository
from app.schemas.lead import (
    LeadCreateRequest,
    LeadNoteCreateRequest,
    LeadTagCreateRequest,
    LeadUpdateRequest,
)

# Valid state machine status progressions
_VALID_TRANSITIONS = {
    LeadStatus.NEW: {LeadStatus.CONTACTED, LeadStatus.LOST},
    LeadStatus.CONTACTED: {LeadStatus.MEETING_SCHEDULED, LeadStatus.LOST},
    LeadStatus.MEETING_SCHEDULED: {LeadStatus.QUALIFIED, LeadStatus.LOST},
    LeadStatus.QUALIFIED: {LeadStatus.PROPOSAL_SENT, LeadStatus.LOST},
    LeadStatus.PROPOSAL_SENT: {LeadStatus.NEGOTIATION, LeadStatus.LOST},
    LeadStatus.NEGOTIATION: {LeadStatus.WON, LeadStatus.LOST},
    LeadStatus.WON: {LeadStatus.ARCHIVED},
    LeadStatus.LOST: {LeadStatus.ARCHIVED},
    LeadStatus.ARCHIVED: set(),
}


class LeadService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.lead_repo = LeadRepository(db)
        self.note_repo = LeadNoteRepository(db)
        self.tag_repo = LeadTagRepository(db)
        self.activity_repo = LeadActivityRepository(db)

    # ── Lead Management ────────────────────────────────────────────────────────

    async def create_lead(self, ctx: RequestContext, data: LeadCreateRequest) -> Lead:
        """Create a new lead, checking for active email/phone duplicates, normalizes fields,
        generates sequential lead numbers, assigns to creator, and registers a CREATED activity.
        """
        # 1. Normalize contact methods
        email = data.email.lower() if data.email else None
        phone = self._normalize_phone(data.phone)

        # Ensure unique constraints in current tenant
        if email and await self.lead_repo.email_exists(ctx, email):
            raise ValidationException(f"A lead with email '{email}' already exists.")
        if phone and await self.lead_repo.phone_exists(ctx, phone):
            raise ValidationException(f"A lead with phone '{phone}' already exists.")

        # 2. Concurrency-safe sequential lead number generation
        lead_number = await self._generate_lead_number(ctx)

        # 3. Fallback currency to organization default settings
        currency = data.currency
        if not data.currency or data.currency == "USD":
            from app.repositories.organization_repository import OrganizationRepository
            org_repo = OrganizationRepository(self.db)
            org_settings = await org_repo.get_settings(ctx.tenant_id)
            if org_settings and org_settings.currency:
                currency = org_settings.currency

        # 4. Instantiate model
        lead = Lead(
            organization_id=ctx.tenant_id,
            lead_number=lead_number,
            created_by=ctx.user.id,
            updated_by=ctx.user.id,
            assigned_to=data.assigned_to or ctx.user.id,
            first_name=data.first_name,
            last_name=data.last_name,
            company_name=data.company_name,
            job_title=data.job_title,
            email=email,
            phone=phone,
            website=self._normalize_website(data.website),
            country=data.country,
            city=data.city,
            source=data.source,
            created_source=data.created_source,
            status=data.status,
            priority=data.priority,
            estimated_value=data.estimated_value,
            currency=currency,
            is_starred=data.is_starred,
            last_activity_at=datetime.now(timezone.utc),
        )

        await self.lead_repo.create(lead)

        # 5. Immutable Activity Log entry
        activity_meta = {
            "created_by": str(ctx.user.id),
            "assigned_to": str(lead.assigned_to) if lead.assigned_to else None,
        }
        await self._log_activity(
            lead_id=lead.id,
            actor_id=ctx.user.id,
            actor_type=ActorType.USER,
            activity_type=LeadActivityType.CREATED,
            metadata=activity_meta,
        )

        # 6. Publish lead.created domain event
        event = DomainEvent(
            event_name="lead.created",
            tenant_id=ctx.tenant_id,
            request_id=ctx.request_id,
            actor_id=ctx.user.id,
            payload={
                "lead_id": str(lead.id),
                "lead_number": lead.lead_number,
                "assigned_to": str(lead.assigned_to) if lead.assigned_to else None,
            },
        )
        await self.db.commit()
        await get_event_publisher().publish(event)
        return lead

    async def update_lead(
        self, ctx: RequestContext, lead_id: uuid.UUID, data: LeadUpdateRequest
    ) -> Lead:
        """Update a lead, checking status transitions, email/phone duplicates, E164/URL normalizations,
        and enforces optimistic locking. Automates last_activity_at bump and logs relevant activities.
        """
        lead = await self.lead_repo.get_by_id(ctx, lead_id)
        if lead is None:
            raise LeadNotFoundException()

        # ── Optimistic Locking Check ──
        if lead.version != data.version:
            raise ConcurrentUpdateException()

        updates: dict[str, Any] = {}
        activities_to_log: list[tuple[LeadActivityType, dict[str, Any]]] = []

        # Validate duplicate email (if updated)
        if data.email is not None:
            email_lower = data.email.lower()
            if email_lower != lead.email:
                if await self.lead_repo.email_exists(ctx, email_lower, exclude_id=lead_id):
                    raise ValidationException(f"A lead with email '{email_lower}' already exists.")
                updates["email"] = email_lower

        # Validate duplicate phone (if updated)
        if data.phone is not None:
            phone_norm = self._normalize_phone(data.phone)
            if phone_norm != lead.phone:
                if await self.lead_repo.phone_exists(ctx, phone_norm, exclude_id=lead_id):
                    raise ValidationException(f"A lead with phone '{phone_norm}' already exists.")
                updates["phone"] = phone_norm

        # Validate status transitions
        if data.status is not None and data.status != lead.status:
            allowed = _VALID_TRANSITIONS.get(lead.status, set())
            if data.status not in allowed:
                raise ValidationException(
                    f"Invalid status transition from '{lead.status.value}' to '{data.status.value}'."
                )
            updates["status"] = data.status
            activities_to_log.append(
                (
                    LeadActivityType.STATUS_CHANGED,
                    {"old_status": lead.status.value, "new_status": data.status.value},
                )
            )

        # Validate assignee changes
        if data.assigned_to is not None and data.assigned_to != lead.assigned_to:
            activities_to_log.append(
                (
                    LeadActivityType.ASSIGNED,
                    {
                        "old_assignee_id": str(lead.assigned_to) if lead.assigned_to else None,
                        "new_assignee_id": str(data.assigned_to) if data.assigned_to else None,
                    },
                )
            )
            updates["assigned_to"] = data.assigned_to

        # Normalize URL
        if data.website is not None:
            updates["website"] = self._normalize_website(data.website)

        # Simple updates
        for field in (
            "first_name",
            "last_name",
            "company_name",
            "job_title",
            "country",
            "city",
            "source",
            "priority",
            "estimated_value",
            "currency",
            "is_starred",
        ):
            val = getattr(data, field)
            if val is not None:
                updates[field] = val

        if updates:
            # Automate last_activity_at bump and update fields
            updates["last_activity_at"] = datetime.now(timezone.utc)
            updates["updated_by"] = ctx.user.id

            # Atomic optimistic locking update query
            stmt = (
                update(Lead)
                .where(
                    Lead.id == lead_id,
                    Lead.organization_id == ctx.tenant_id,
                    Lead.version == lead.version,
                )
                .values(**updates, version=lead.version + 1)
            )
            result = await self.db.execute(stmt)
            if result.rowcount == 0:
                raise ConcurrentUpdateException()

            # Record generic update event
            activities_to_log.append(
                (
                    LeadActivityType.UPDATED,
                    {"updated_fields": list(updates.keys())},
                )
            )

            # Log all activities gathered
            for act_type, meta in activities_to_log:
                await self._log_activity(
                    lead_id=lead_id,
                    actor_id=ctx.user.id,
                    actor_type=ActorType.USER,
                    activity_type=act_type,
                    metadata=meta,
                )

            # Publish lead.updated event
            event = DomainEvent(
                event_name="lead.updated",
                tenant_id=ctx.tenant_id,
                request_id=ctx.request_id,
                actor_id=ctx.user.id,
                payload={
                    "lead_id": str(lead_id),
                    "updated_fields": list(updates.keys()),
                }
            )
            await self.db.commit()
            # Refresh lead model reference to reflect version and fields
            await self.db.refresh(lead)
            await get_event_publisher().publish(event)

        return lead

    async def soft_delete_lead(self, ctx: RequestContext, lead_id: uuid.UUID) -> None:
        """Soft delete a lead, checking tenant validity, and cascade soft-deletes associated tasks."""
        lead = await self.lead_repo.get_by_id(ctx, lead_id)
        if lead is None:
            raise LeadNotFoundException()

        await self.lead_repo.soft_delete(ctx, lead_id)

        # Cascade soft-delete all active tasks belonging to this lead
        from app.repositories.task_repository import TaskRepository
        task_repo = TaskRepository(self.db)
        await task_repo.soft_delete_for_lead(ctx, lead_id)

        # Publish lead.deleted event
        event = DomainEvent(
            event_name="lead.deleted",
            tenant_id=ctx.tenant_id,
            request_id=ctx.request_id,
            actor_id=ctx.user.id,
            payload={
                "lead_id": str(lead_id),
            }
        )
        await self.db.commit()
        await get_event_publisher().publish(event)

    # ── Notes Management ───────────────────────────────────────────────────────

    async def create_note(
        self, ctx: RequestContext, lead_id: uuid.UUID, data: LeadNoteCreateRequest
    ) -> LeadNote:
        """Add a note to a lead, updating last_activity_at and logging activity."""
        lead = await self.lead_repo.get_by_id(ctx, lead_id)
        if lead is None:
            raise LeadNotFoundException()

        note = LeadNote(
            lead_id=lead_id,
            author_id=ctx.user.id,
            content=data.content,
        )
        await self.note_repo.create(note)

        # Update last_activity_at
        lead.last_activity_at = datetime.now(timezone.utc)
        lead.updated_by = ctx.user.id
        self.db.add(lead)

        # Log timeline activity
        await self._log_activity(
            lead_id=lead_id,
            actor_id=ctx.user.id,
            actor_type=ActorType.USER,
            activity_type=LeadActivityType.NOTE_ADDED,
            metadata={"note_id": str(note.id), "excerpt": data.content[:100]},
        )

        await self.db.commit()
        return note

    async def list_notes(self, ctx: RequestContext, lead_id: uuid.UUID) -> list[LeadNote]:
        """Fetch all notes for a specific lead."""
        lead = await self.lead_repo.get_by_id(ctx, lead_id)
        if lead is None:
            raise LeadNotFoundException()

        return await self.note_repo.list_for_lead(ctx, lead_id)

    # ── Tag Management ─────────────────────────────────────────────────────────

    async def create_tag(self, ctx: RequestContext, data: LeadTagCreateRequest) -> LeadTag:
        """Create a new tag within the tenant."""
        existing = await self.tag_repo.get_tag_by_name(ctx, data.name)
        if existing is not None:
            return existing

        tag = LeadTag(
            organization_id=ctx.tenant_id,
            name=data.name,
            color=data.color,
        )
        await self.tag_repo.create_tag(tag)
        await self.db.commit()
        return tag

    async def assign_tag_to_lead(
        self, ctx: RequestContext, lead_id: uuid.UUID, tag_id: uuid.UUID
    ) -> None:
        """Assign tag, enforcing cross-tenant security locks and activity logs."""
        lead = await self.lead_repo.get_by_id(ctx, lead_id)
        if lead is None:
            raise LeadNotFoundException()

        tag = await self.tag_repo.get_tag_by_id(ctx, tag_id)
        if tag is None:
            raise ValidationException("Tag not found in this organization.")

        assigned = await self.tag_repo.assign_tag(lead_id, tag_id, ctx.user.id)
        if assigned:
            # Update last_activity_at
            lead.last_activity_at = datetime.now(timezone.utc)
            lead.updated_by = ctx.user.id
            self.db.add(lead)

            # Log activity
            await self._log_activity(
                lead_id=lead_id,
                actor_id=ctx.user.id,
                actor_type=ActorType.USER,
                activity_type=LeadActivityType.TAG_ADDED,
                metadata={"tag_id": str(tag_id), "tag_name": tag.name},
            )
            await self.db.commit()

    async def remove_tag_from_lead(
        self, ctx: RequestContext, lead_id: uuid.UUID, tag_id: uuid.UUID
    ) -> None:
        """Remove a tag, logging activity and updating activity timestamp."""
        lead = await self.lead_repo.get_by_id(ctx, lead_id)
        if lead is None:
            raise LeadNotFoundException()

        tag = await self.tag_repo.get_tag_by_id(ctx, tag_id)
        if tag is None:
            raise ValidationException("Tag not found in this organization.")

        removed = await self.tag_repo.remove_tag(lead_id, tag_id)
        if removed:
            # Update last_activity_at
            lead.last_activity_at = datetime.now(timezone.utc)
            lead.updated_by = ctx.user.id
            self.db.add(lead)

            # Log activity
            await self._log_activity(
                lead_id=lead_id,
                actor_id=ctx.user.id,
                actor_type=ActorType.USER,
                activity_type=LeadActivityType.TAG_REMOVED,
                metadata={"tag_id": str(tag_id), "tag_name": tag.name},
            )
            await self.db.commit()

    # ── Activity Timeline ──────────────────────────────────────────────────────

    async def list_activities(self, ctx: RequestContext, lead_id: uuid.UUID) -> list[LeadActivity]:
        """Fetch lead activity logs sorted newest-first."""
        lead = await self.lead_repo.get_by_id(ctx, lead_id)
        if lead is None:
            raise LeadNotFoundException()

        return await self.activity_repo.list_for_lead(ctx, lead_id)

    # ── Helper Methods ─────────────────────────────────────────────────────────

    async def _generate_lead_number(self, ctx: RequestContext) -> int:
        """Acquire a row lock FOR UPDATE on the sequence table and increment atomically."""
        stmt = (
            select(OrganizationSequence.next_lead_number)
            .where(OrganizationSequence.organization_id == ctx.tenant_id)
            .with_for_update()
        )
        res = await self.db.execute(stmt)
        next_num = res.scalar()

        if next_num is None:
            # Fallback for organizations that exist without sequences (e.g. brownfield)
            seq = OrganizationSequence(
                organization_id=ctx.tenant_id, next_lead_number=1002
            )
            self.db.add(seq)
            await self.db.flush()
            return 1001
        else:
            await self.db.execute(
                update(OrganizationSequence)
                .where(OrganizationSequence.organization_id == ctx.tenant_id)
                .values(next_lead_number=next_num + 1)
            )
            await self.db.flush()
            return next_num

    @staticmethod
    def _normalize_phone(phone: str | None) -> str | None:
        if not phone:
            return None
        # Remove anything that isn't a digit or a leading plus sign
        cleaned = "".join([c for c in phone if c.isdigit() or c == "+"])
        if cleaned.startswith("+"):
            return "+" + cleaned[1:].replace("+", "")
        return cleaned.replace("+", "")

    @staticmethod
    def _normalize_website(url: str | None) -> str | None:
        if not url:
            return None
        if not (url.startswith("http://") or url.startswith("https://")):
            return "https://" + url
        return url

    async def _log_activity(
        self,
        lead_id: uuid.UUID,
        actor_id: uuid.UUID | None,
        actor_type: ActorType,
        activity_type: LeadActivityType,
        metadata: dict[str, Any],
    ) -> None:
        """Log a timeline activity. Appends strictly (immutable logs).

        Enforces metadata schemas defined in plan.
        """
        # Validate metadata schema based on action type
        if activity_type == LeadActivityType.STATUS_CHANGED:
            if "old_status" not in metadata or "new_status" not in metadata:
                raise ValueError("STATUS_CHANGED activity requires 'old_status' and 'new_status'")
        elif activity_type == LeadActivityType.ASSIGNED:
            if "old_assignee_id" not in metadata or "new_assignee_id" not in metadata:
                raise ValueError("ASSIGNED activity requires 'old_assignee_id' and 'new_assignee_id'")
        elif activity_type == LeadActivityType.TAG_ADDED or activity_type == LeadActivityType.TAG_REMOVED:
            if "tag_id" not in metadata or "tag_name" not in metadata:
                raise ValueError("TAG activity requires 'tag_id' and 'tag_name'")
        elif activity_type == LeadActivityType.NOTE_ADDED:
            if "note_id" not in metadata or "excerpt" not in metadata:
                raise ValueError("NOTE_ADDED activity requires 'note_id' and 'excerpt'")

        activity = LeadActivity(
            lead_id=lead_id,
            actor_id=actor_id,
            actor_type=actor_type,
            activity_type=activity_type,
            event_metadata=metadata,
            metadata_version=1,
        )
        await self.activity_repo.create_activity(activity)
