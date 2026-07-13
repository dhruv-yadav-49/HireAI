import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import delete, update, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.exceptions import (
    ConcurrentUpdateException,
    TaskNotFoundException,
    ValidationException,
    WorkflowNotFoundException,
)
from app.models.enums import ActorType, WorkflowTriggerType
from app.models.workflow import Workflow, WorkflowCondition, WorkflowAction
from app.models.workflow_execution import WorkflowExecution
from app.repositories.workflow_repository import WorkflowRepository
from app.repositories.workflow_execution_repository import WorkflowExecutionRepository
from app.schemas.workflow import WorkflowCreateRequest, WorkflowUpdateRequest
from app.services.workflow_executor import WorkflowExecutor, WorkflowTriggerContext


class WorkflowService:
    """Core domain logic coordinator for managing Workflow Automation setups."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = WorkflowRepository(db)
        self.execution_repo = WorkflowExecutionRepository(db)

    async def create_workflow(self, ctx: RequestContext, data: WorkflowCreateRequest) -> Workflow:
        # Create workflow base
        workflow = Workflow(
            organization_id=ctx.tenant_id,
            name=data.name,
            description=data.description,
            trigger_type=data.trigger_type,
            trigger_filter=data.trigger_filter,
            retry_policy=data.retry_policy,
            enabled=True,
            created_by=ctx.user.id,
            updated_by=ctx.user.id,
        )
        await self.repo.create(workflow)

        # Create conditions
        for cond_schema in data.conditions:
            cond = WorkflowCondition(
                workflow_id=workflow.id,
                field=cond_schema.field,
                operator=cond_schema.operator,
                value=cond_schema.value,
                value_type=cond_schema.value_type,
                group_id=cond_schema.group_id,
                logical_operator=cond_schema.logical_operator,
                order=cond_schema.order,
            )
            self.db.add(cond)

        # Create actions
        for act_schema in data.actions:
            act = WorkflowAction(
                workflow_id=workflow.id,
                action_type=act_schema.action_type,
                configuration=act_schema.configuration,
                retryable=act_schema.retryable,
                max_retries=act_schema.max_retries,
                execution_mode=act_schema.execution_mode,
                order=act_schema.order,
            )
            self.db.add(act)

        await self.db.commit()
        # Eagerly load conditions and actions to prevent LazyLoad/MissingGreenlet errors in serialization
        stmt = (
            select(Workflow)
            .options(selectinload(Workflow.conditions), selectinload(Workflow.actions))
            .where(Workflow.id == workflow.id)
        )
        res = await self.db.execute(stmt)
        return res.scalar_one()

    async def update_workflow(
        self, ctx: RequestContext, workflow_id: uuid.UUID, data: WorkflowUpdateRequest
    ) -> Workflow:
        workflow = await self.repo.get_by_id(ctx, workflow_id)
        if workflow is None:
            raise WorkflowNotFoundException()

        # Optimistic locking check
        if workflow.version != data.version:
            raise ConcurrentUpdateException()

        updates: dict[str, Any] = {}
        for field in ("name", "description", "enabled", "trigger_type", "trigger_filter", "retry_policy"):
            val = getattr(data, field)
            if val is not None:
                updates[field] = val

        if updates or data.conditions is not None or data.actions is not None:
            updates["updated_by"] = ctx.user.id
            updates["updated_at"] = datetime.now(timezone.utc)

            # Perform atomic update
            stmt = (
                update(Workflow)
                .where(
                    Workflow.id == workflow_id,
                    Workflow.organization_id == ctx.tenant_id,
                    Workflow.version == workflow.version,
                )
                .values(**updates, version=workflow.version + 1)
            )
            res = await self.db.execute(stmt)
            if res.rowcount == 0:
                raise ConcurrentUpdateException()

            # Clear and rebuild conditions if updated
            if data.conditions is not None:
                await self.db.execute(
                    delete(WorkflowCondition).where(WorkflowCondition.workflow_id == workflow_id)
                )
                for cond_schema in data.conditions:
                    cond = WorkflowCondition(
                        workflow_id=workflow_id,
                        field=cond_schema.field,
                        operator=cond_schema.operator,
                        value=cond_schema.value,
                        value_type=cond_schema.value_type,
                        group_id=cond_schema.group_id,
                        logical_operator=cond_schema.logical_operator,
                        order=cond_schema.order,
                    )
                    self.db.add(cond)

            # Clear and rebuild actions if updated
            if data.actions is not None:
                await self.db.execute(
                    delete(WorkflowAction).where(WorkflowAction.workflow_id == workflow_id)
                )
                for act_schema in data.actions:
                    act = WorkflowAction(
                        workflow_id=workflow_id,
                        action_type=act_schema.action_type,
                        configuration=act_schema.configuration,
                        retryable=act_schema.retryable,
                        max_retries=act_schema.max_retries,
                        execution_mode=act_schema.execution_mode,
                        order=act_schema.order,
                    )
                    self.db.add(act)

            await self.db.commit()
            # Eagerly load conditions and actions to prevent LazyLoad/MissingGreenlet errors in serialization
            stmt = (
                select(Workflow)
                .options(selectinload(Workflow.conditions), selectinload(Workflow.actions))
                .where(Workflow.id == workflow_id)
            )
            res = await self.db.execute(stmt)
            return res.scalar_one()

        return workflow

    async def enable_workflow(self, ctx: RequestContext, workflow_id: uuid.UUID, version: int) -> Workflow:
        return await self.update_workflow(
            ctx, workflow_id, WorkflowUpdateRequest(version=version, enabled=True)
        )

    async def disable_workflow(self, ctx: RequestContext, workflow_id: uuid.UUID, version: int) -> Workflow:
        return await self.update_workflow(
            ctx, workflow_id, WorkflowUpdateRequest(version=version, enabled=False)
        )

    async def execute_manually(
        self, ctx: RequestContext, workflow_id: uuid.UUID, entity_type: str, entity_id: uuid.UUID
    ) -> WorkflowExecution:
        """Forces immediate execution of a workflow bypassing condition engines."""
        workflow = await self.repo.get_by_id(ctx, workflow_id)
        if workflow is None:
            raise WorkflowNotFoundException()

        if not workflow.enabled:
            raise ValidationException("Disabled workflows cannot be executed.")

        # Resolve the dynamic details to populate trigger context payload
        payload = {}
        if entity_type == "LEAD":
            from app.repositories.lead_repository import LeadRepository
            lead_repo = LeadRepository(self.db)
            lead = await lead_repo.get_by_id(ctx, entity_id)
            if lead is not None:
                payload = {
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
            task_repo = TaskRepository(self.db)
            task = await task_repo.get_by_id(ctx, entity_id)
            if task is not None:
                payload = {
                    "title": task.title,
                    "description": task.description,
                    "status": task.status.value if task.status else None,
                    "priority": task.priority.value if task.priority else None,
                }

        trigger_ctx = WorkflowTriggerContext(
            event_id=uuid.uuid4(),
            trigger_type=WorkflowTriggerType.MANUAL,
            entity_type=entity_type,
            entity_id=entity_id,
            tenant_id=ctx.tenant_id,
            request_id=ctx.request_id,
            actor_id=ctx.user.id,
            payload=payload,
            before=payload,
            after=payload,
        )

        executor = WorkflowExecutor(self.db)
        execution = await executor.execute(ctx, workflow, trigger_ctx)
        return execution
