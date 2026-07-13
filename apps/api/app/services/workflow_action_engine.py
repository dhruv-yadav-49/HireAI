import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.exceptions import ValidationException
from app.models.enums import WorkflowActionType
from app.schemas.lead import LeadNoteCreateRequest, LeadUpdateRequest
from app.schemas.task import TaskCreateRequest
from app.services.lead_service import LeadService
from app.services.task_service import TaskService
from app.repositories.lead_tag_repository import LeadTagRepository
from app.models.lead_tag import LeadTag


# ── Handler Protocol & Implementations ────────────────────────────────────────

class ActionHandler(Protocol):
    async def execute(
        self,
        ctx: RequestContext,
        config: dict[str, Any],
        entity_id: uuid.UUID,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Executes a workflow action using config details and target entity."""
        ...


class CreateTaskHandler:
    async def execute(
        self,
        ctx: RequestContext,
        config: dict[str, Any],
        entity_id: uuid.UUID,
        db: AsyncSession,
    ) -> dict[str, Any]:
        task_service = TaskService(db)
        due_at = None
        if config.get("offset_hours") is not None:
            due_at = datetime.now(timezone.utc) + timedelta(hours=config["offset_hours"])

        req = TaskCreateRequest(
            lead_id=entity_id,
            title=config["title"],
            description=config.get("description"),
            priority=config.get("priority", "LOW"),
            type=config.get("type", "FOLLOW_UP"),
            due_at=due_at,
            reminder_at=None,
        )
        task = await task_service.create_task(ctx, req)
        return {
            "task_id": str(task.id),
            "title": task.title,
            "due_at": task.due_at.isoformat() if task.due_at else None,
        }


class UpdateLeadHandler:
    async def execute(
        self,
        ctx: RequestContext,
        config: dict[str, Any],
        entity_id: uuid.UUID,
        db: AsyncSession,
    ) -> dict[str, Any]:
        lead_service = LeadService(db)
        lead = await lead_service.lead_repo.get_by_id(ctx, entity_id)
        if lead is None:
            raise ValidationException("Lead not found during update action execution.")

        req = LeadUpdateRequest(
            version=lead.version,
            first_name=config.get("first_name"),
            last_name=config.get("last_name"),
            company_name=config.get("company_name"),
            job_title=config.get("job_title"),
            city=config.get("city"),
            country=config.get("country"),
            priority=config.get("priority"),
        )
        updated_lead = await lead_service.update_lead(ctx, entity_id, req)
        return {"lead_id": str(updated_lead.id), "version": updated_lead.version}


class ChangeStatusHandler:
    async def execute(
        self,
        ctx: RequestContext,
        config: dict[str, Any],
        entity_id: uuid.UUID,
        db: AsyncSession,
    ) -> dict[str, Any]:
        lead_service = LeadService(db)
        lead = await lead_service.lead_repo.get_by_id(ctx, entity_id)
        if lead is None:
            raise ValidationException("Lead not found during status change action execution.")

        req = LeadUpdateRequest(
            version=lead.version,
            status=config["status"],
        )
        updated_lead = await lead_service.update_lead(ctx, entity_id, req)
        return {
            "lead_id": str(updated_lead.id),
            "old_status": lead.status.value,
            "new_status": updated_lead.status.value,
        }


class AssignUserHandler:
    async def execute(
        self,
        ctx: RequestContext,
        config: dict[str, Any],
        entity_id: uuid.UUID,
        db: AsyncSession,
    ) -> dict[str, Any]:
        lead_service = LeadService(db)
        lead = await lead_service.lead_repo.get_by_id(ctx, entity_id)
        if lead is None:
            raise ValidationException("Lead not found during assign user action execution.")

        req = LeadUpdateRequest(
            version=lead.version,
            assigned_to=uuid.UUID(config["assigned_to"]),
        )
        updated_lead = await lead_service.update_lead(ctx, entity_id, req)
        return {
            "lead_id": str(updated_lead.id),
            "assigned_to": str(updated_lead.assigned_to),
        }


class AddNoteHandler:
    async def execute(
        self,
        ctx: RequestContext,
        config: dict[str, Any],
        entity_id: uuid.UUID,
        db: AsyncSession,
    ) -> dict[str, Any]:
        lead_service = LeadService(db)
        req = LeadNoteCreateRequest(content=config["content"])
        note = await lead_service.create_note(ctx, entity_id, req)
        return {"note_id": str(note.id), "excerpt": note.content[:100]}


class AddTagHandler:
    async def execute(
        self,
        ctx: RequestContext,
        config: dict[str, Any],
        entity_id: uuid.UUID,
        db: AsyncSession,
    ) -> dict[str, Any]:
        tag_repo = LeadTagRepository(db)
        lead_service = LeadService(db)
        tag_name = config["tag_name"]

        tag = await tag_repo.get_tag_by_name(ctx, tag_name)
        if tag is None:
            tag = LeadTag(
                organization_id=ctx.tenant_id,
                name=tag_name,
                color="#FFFFFF",
            )
            await tag_repo.create_tag(tag)

        await lead_service.assign_tag_to_lead(ctx, entity_id, tag.id)
        return {"tag_id": str(tag.id), "tag_name": tag.name}


class SendEmailHandler:
    async def execute(
        self,
        ctx: RequestContext,
        config: dict[str, Any],
        entity_id: uuid.UUID,
        db: AsyncSession,
    ) -> dict[str, Any]:
        from app.models.lead import Lead
        from app.models.task import Task
        from app.models.enums import CommunicationChannel, RecipientType, CommunicationDirection
        from app.schemas.communication import CommunicationSendRequest
        from app.services.communication_service import CommunicationService

        lead_id = None
        task_id = None

        lead_check = await db.get(Lead, entity_id)
        if lead_check:
            lead_id = entity_id
        else:
            task_check = await db.get(Task, entity_id)
            if task_check:
                task_id = entity_id
                lead_id = task_check.lead_id

        # Resolve recipient
        recipient = config.get("recipient")
        recipient_type = RecipientType.RAW
        if not recipient and lead_id:
            recipient = "lead.email"
            recipient_type = RecipientType.LEAD

        req = CommunicationSendRequest(
            channel=CommunicationChannel.EMAIL,
            recipient=recipient or "lead.email",
            recipient_type=recipient_type,
            lead_id=lead_id,
            task_id=task_id,
            template_name=config.get("template_name"),
            subject=config.get("subject"),
            body=config.get("body"),
            attachments_json=config.get("attachments", []),
            priority=config.get("priority", "NORMAL"),
            direction=CommunicationDirection.OUTBOUND,
            conversation_id=config.get("conversation_id"),
            parent_communication_id=config.get("parent_communication_id"),
        )

        comms_service = CommunicationService(db)
        # Use deterministic idempotency key to prevent double queueing per execution request
        idempotency_key = f"email_{ctx.request_id}_{entity_id}_{config.get('template_name', 'raw')}"
        com = await comms_service.queue_communication(ctx, req, idempotency_key=idempotency_key)
        return {"communication_id": str(com.id), "recipient": com.recipient, "status": com.status.value}


class SendWhatsAppHandler:
    async def execute(
        self,
        ctx: RequestContext,
        config: dict[str, Any],
        entity_id: uuid.UUID,
        db: AsyncSession,
    ) -> dict[str, Any]:
        from app.models.lead import Lead
        from app.models.task import Task
        from app.models.enums import CommunicationChannel, RecipientType, CommunicationDirection
        from app.schemas.communication import CommunicationSendRequest
        from app.services.communication_service import CommunicationService

        lead_id = None
        task_id = None

        lead_check = await db.get(Lead, entity_id)
        if lead_check:
            lead_id = entity_id
        else:
            task_check = await db.get(Task, entity_id)
            if task_check:
                task_id = entity_id
                lead_id = task_check.lead_id

        # Resolve recipient
        recipient = config.get("recipient")
        recipient_type = RecipientType.RAW
        if not recipient and lead_id:
            recipient = "lead.phone"
            recipient_type = RecipientType.LEAD

        req = CommunicationSendRequest(
            channel=CommunicationChannel.WHATSAPP,
            recipient=recipient or "lead.phone",
            recipient_type=recipient_type,
            lead_id=lead_id,
            task_id=task_id,
            template_name=config.get("template_name"),
            body=config.get("body"),
            attachments_json=config.get("attachments", []),
            priority=config.get("priority", "NORMAL"),
            direction=CommunicationDirection.OUTBOUND,
            conversation_id=config.get("conversation_id"),
            parent_communication_id=config.get("parent_communication_id"),
        )

        coms_service = CommunicationService(db)
        idempotency_key = f"whatsapp_{ctx.request_id}_{entity_id}_{config.get('template_name', 'raw')}"
        com = await coms_service.queue_communication(ctx, req, idempotency_key=idempotency_key)
        return {"communication_id": str(com.id), "recipient": com.recipient, "status": com.status.value}


# ── Action Handlers Registry ──────────────────────────────────────────────────

ACTION_HANDLERS: dict[WorkflowActionType, ActionHandler] = {
    WorkflowActionType.CREATE_TASK: CreateTaskHandler(),
    WorkflowActionType.UPDATE_LEAD: UpdateLeadHandler(),
    WorkflowActionType.CHANGE_STATUS: ChangeStatusHandler(),
    WorkflowActionType.ASSIGN_USER: AssignUserHandler(),
    WorkflowActionType.ADD_NOTE: AddNoteHandler(),
    WorkflowActionType.ADD_TAG: AddTagHandler(),
    WorkflowActionType.SEND_EMAIL: SendEmailHandler(),
    WorkflowActionType.SEND_WHATSAPP: SendWhatsAppHandler(),
}


class WorkflowActionEngine:
    """Action dispatcher manager that routes automation items to their registry handlers."""

    @staticmethod
    async def execute_action(
        ctx: RequestContext,
        action_type: WorkflowActionType,
        configuration: dict[str, Any],
        entity_id: uuid.UUID,
        db: AsyncSession,
    ) -> dict[str, Any]:
        handler = ACTION_HANDLERS.get(action_type)
        if handler is None:
            raise NotImplementedError(f"No action handler registered for type: '{action_type.value}'")

        return await handler.execute(ctx, configuration, entity_id, db)
