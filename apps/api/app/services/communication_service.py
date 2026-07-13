import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.exceptions import ValidationException
from app.models.enums import (
    CommunicationChannel,
    CommunicationStatus,
    CommunicationDirection,
    RecipientType,
    DeliveryEvent,
)
from app.models.communication import Communication
from app.models.communication_template import CommunicationTemplate
from app.models.organization import Organization
from app.models.user import User
from app.models.lead import Lead
from app.models.task import Task
from app.schemas.communication import CommunicationSendRequest
from app.services.template_engine import TemplateEngine
from app.services.delivery_tracker import DeliveryTracker

logger = logging.getLogger(__name__)


class CommunicationService:
    """Core coordinator for template rendering, dynamic context loading, and communication queuing."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def queue_communication(
        self,
        ctx: RequestContext,
        req: CommunicationSendRequest,
        idempotency_key: Optional[str] = None
    ) -> Communication:
        """Processes request payload, resolves variable templates, and queues outbound communication."""
        
        # 1. Enforce unique Idempotency Key
        idemp_key = idempotency_key or req.subject or str(uuid.uuid4())
        # Check duplicate
        dup_stmt = select(Communication).where(
            Communication.organization_id == ctx.tenant_id,
            Communication.idempotency_key == idemp_key
        )
        dup_res = await self.db.execute(dup_stmt)
        duplicate = dup_res.scalar()
        if duplicate is not None:
            # Idempotent match: return already-queued message
            return duplicate

        # 2. Resolve recipient phone/email target from entity if specified
        resolved_recipient = req.recipient
        if req.recipient_type == RecipientType.LEAD and req.lead_id:
            lead = await self.db.get(Lead, req.lead_id)
            if lead:
                if req.channel == CommunicationChannel.EMAIL:
                    resolved_recipient = lead.email or resolved_recipient
                else:
                    resolved_recipient = lead.phone or resolved_recipient
        elif req.recipient_type == RecipientType.USER and req.lead_id:
            # Re-routed user mapping if needed (for simplicity, use user.email or default)
            pass

        # 3. Resolve template details if template target supplied
        template = None
        if req.template_id:
            template = await self.db.get(CommunicationTemplate, req.template_id)
        elif req.template_name:
            stmt = select(CommunicationTemplate).where(
                CommunicationTemplate.organization_id == ctx.tenant_id,
                CommunicationTemplate.name == req.template_name,
                CommunicationTemplate.channel == req.channel,
                CommunicationTemplate.deleted_at.is_(None)
            )
            res = await self.db.execute(stmt)
            template = res.scalar()

        # 4. Resolve dot-notated template contexts from database entities
        lead_obj = None
        if req.lead_id:
            lead_obj = await self.db.get(Lead, req.lead_id)
        task_obj = None
        if req.task_id:
            task_obj = await self.db.get(Task, req.task_id)
        
        org_obj = await self.db.get(Organization, ctx.tenant_id)
        user_obj = None
        if ctx.user:
            user_obj = await self.db.get(User, ctx.user.id)

        rendering_context = {
            "lead": lead_obj,
            "task": task_obj,
            "organization": org_obj,
            "user": user_obj
        }

        # Render content
        rendered_subj = req.subject
        rendered_body = req.body

        template_snap = None
        if template:
            if not template.enabled:
                raise ValidationException(f"Template '{template.name}' is disabled.")
            
            # Use template structures
            raw_body = template.body_template
            raw_subj = template.subject_template
            
            # Render using engine
            rendered_body, rendered_subj = TemplateEngine.render(
                raw_body, raw_subj, rendering_context, template.version
            )
            
            # Construct snapshot dictionary
            template_snap = {
                "id": str(template.id),
                "name": template.name,
                "version": template.version,
                "subject_template": template.subject_template,
                "body_template": template.body_template,
                "variables": template.variables_json
            }
        else:
            # Inline raw send — perform simple replace-render if placeholders are present
            if rendered_body:
                rendered_body, rendered_subj = TemplateEngine.render(
                    rendered_body, rendered_subj, rendering_context, 1
                )

        if not rendered_body:
            raise ValidationException("Communication body cannot be resolved or empty.")

        # Create communication record
        communication = Communication(
            organization_id=ctx.tenant_id,
            lead_id=req.lead_id,
            task_id=req.task_id,
            template_id=template.id if template else None,
            channel=req.channel,
            recipient=resolved_recipient,
            recipient_type=req.recipient_type,
            direction=req.direction or CommunicationDirection.OUTBOUND,
            conversation_id=req.conversation_id or uuid.uuid4(), # New thread if not supplied
            parent_communication_id=req.parent_communication_id,
            subject=req.subject,
            body=req.body or rendered_body,
            rendered_subject=rendered_subj,
            rendered_body=rendered_body,
            template_snapshot=template_snap,
            attachments_json=req.attachments_json or [],
            status=CommunicationStatus.QUEUED,
            priority=req.priority or CommunicationPriority.NORMAL,
            idempotency_key=idemp_key,
            created_by=ctx.user.id if ctx.user else None,
        )

        self.db.add(communication)
        await self.db.flush()

        # Log QUEUED event
        await DeliveryTracker.log_delivery_event(
            self.db,
            communication,
            DeliveryEvent.QUEUED
        )

        await self.db.commit()
        return communication
