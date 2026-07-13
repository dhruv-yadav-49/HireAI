import uuid
import logging
from typing import Any

from app.core.context import RequestContext
from app.core.events import DomainEvent
from app.db.session import AsyncSessionFactory
from app.models.enums import WorkflowTriggerType
from app.repositories.workflow_repository import WorkflowRepository
from app.services.workflow_executor import WorkflowExecutor, WorkflowTriggerContext

logger = logging.getLogger(__name__)

# Map DomainEvent names to WorkflowTriggerTypes
EVENT_TRIGGER_MAP = {
    "lead.created": WorkflowTriggerType.LEAD_CREATED,
    "lead.updated": WorkflowTriggerType.LEAD_UPDATED,
    "task.created": WorkflowTriggerType.TASK_CREATED,
    "task.status_changed": WorkflowTriggerType.TASK_COMPLETED,
    "lead.inactive": WorkflowTriggerType.LEAD_INACTIVE,
    "task.due_soon": WorkflowTriggerType.TASK_DUE_SOON,
}


async def workflow_event_subscriber(event: DomainEvent) -> None:
    """Interceptors that receive domain event dispatches and trigger workflows."""
    # 1. Resolve event to trigger type
    trigger_type = EVENT_TRIGGER_MAP.get(event.event_name)
    if trigger_type is None:
        return

    # Special transition check for Task completed
    if event.event_name == "task.status_changed":
        new_status = event.payload.get("new_status")
        if new_status == "COMPLETED":
            trigger_type = WorkflowTriggerType.TASK_COMPLETED
        else:
            return  # Trigger is ignored for other status changes

    # 2. Open independent scoped session to avoid transaction pollution
    async with AsyncSessionFactory() as db:
        workflow_repo = WorkflowRepository(db)

        # 3. Resolve active workflows matching trigger type on tenant
        workflows = await workflow_repo.get_enabled_by_trigger(event.tenant_id, trigger_type)
        if not workflows:
            return

        # 4. Formulate RequestContext and TriggerContext
        class MockRequestContext:
            def __init__(self, tenant_id, user_id, request_id):
                self._tenant_id = tenant_id
                self.user = type("MockUser", (), {"id": user_id})()
                self.organization = type("MockOrg", (), {"id": tenant_id})()
                self.request_id = request_id

            @property
            def tenant_id(self):
                return self._tenant_id

        user_id = event.actor_id
        if user_id is None:
            # System event: resolve the organization owner to use as created_by
            from sqlalchemy import select as sa_select
            from app.models.organization import Organization
            org_result = await db.execute(
                sa_select(Organization.owner_id).where(Organization.id == event.tenant_id)
            )
            user_id = org_result.scalar() or uuid.uuid4()  # Fallback to random only if org not found

        ctx = MockRequestContext(
            tenant_id=event.tenant_id,
            user_id=user_id,
            request_id=event.request_id or uuid.uuid4(),
        )

        executor = WorkflowExecutor(db)

        entity_type = "LEAD" if "lead" in event.event_name else "TASK"
        entity_id_str = event.payload.get("lead_id") or event.payload.get("task_id")
        if not entity_id_str:
            return
        entity_id = uuid.UUID(entity_id_str)

        # Fetch current database state to populate payload values
        db_payload = {}
        if entity_type == "LEAD":
            from app.repositories.lead_repository import LeadRepository
            lead_repo = LeadRepository(db)
            lead = await lead_repo.get_by_id(ctx, entity_id)
            if lead is not None:
                db_payload = {
                    "first_name": lead.first_name,
                    "last_name": lead.last_name,
                    "company_name": lead.company_name,
                    "job_title": lead.job_title,
                    "email": lead.email,
                    "phone": lead.phone,
                    "website": lead.website,
                    "status": lead.status.value if lead.status else None,
                    "priority": lead.priority.value if lead.priority else None,
                    "estimated_value": float(lead.estimated_value) if lead.estimated_value else None,
                }
        elif entity_type == "TASK":
            from app.repositories.task_repository import TaskRepository
            task_repo = TaskRepository(db)
            task = await task_repo.get_by_id(ctx, entity_id)
            if task is not None:
                db_payload = {
                    "title": task.title,
                    "description": task.description,
                    "status": task.status.value if task.status else None,
                    "priority": task.priority.value if task.priority else None,
                }

        # Resolve payload structure
        before_state = event.payload.get("before") or db_payload
        after_state = event.payload.get("after") or db_payload

        trigger_ctx = WorkflowTriggerContext(
            event_id=event.event_id,
            trigger_type=trigger_type,
            entity_type=entity_type,
            entity_id=entity_id,
            tenant_id=event.tenant_id,
            request_id=event.request_id,
            actor_id=event.actor_id,
            trigger_source="USER" if event.actor_id else "SYSTEM",
            execution_mode="SYNC",
            payload=after_state,
            before=before_state,
            after=after_state,
        )

        # 5. Execute workflows loop
        for workflow in workflows:
            # Pre-filter check using trigger_filter config if specified
            if workflow.trigger_filter:
                match = True
                for filter_key, filter_val in workflow.trigger_filter.items():
                    actual = after_state.get(filter_key)
                    if hasattr(actual, "value"):
                        actual = actual.value
                    if isinstance(filter_val, list):
                        if actual not in filter_val:
                            match = False
                            break
                    elif actual != filter_val:
                        match = False
                        break
                if not match:
                    continue  # Pre-filter mismatch, skip executor invocation

            try:
                await executor.execute(ctx, workflow, trigger_ctx)
            except Exception as exc:
                logger.error(f"Failed to execute workflow {workflow.id}: {str(exc)}")
