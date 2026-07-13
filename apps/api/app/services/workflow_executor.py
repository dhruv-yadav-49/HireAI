import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.exceptions import ValidationException
from app.models.enums import ActorType, StepExecutionStatus, WorkflowExecutionStatus, WorkflowTriggerType
from app.models.workflow import Workflow
from app.models.workflow_execution import WorkflowExecution, WorkflowExecutionStep
from app.repositories.workflow_execution_repository import WorkflowExecutionRepository
from app.services.workflow_condition_engine import WorkflowConditionEngine
from app.services.workflow_action_engine import WorkflowActionEngine


class WorkflowTriggerContext(BaseModel):
    event_id: uuid.UUID
    trigger_type: WorkflowTriggerType
    entity_type: str  # "LEAD" | "TASK"
    entity_id: uuid.UUID
    tenant_id: uuid.UUID
    request_id: Optional[uuid.UUID] = None
    actor_id: Optional[uuid.UUID] = None
    trigger_source: Optional[str] = None
    execution_mode: str = "SYNC"
    payload: dict[str, Any] = Field(default_factory=dict)
    before: Optional[dict[str, Any]] = None
    after: dict[str, Any]


class WorkflowExecutor:
    """Orchestrates the lifecycle of workflow execution runs."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.execution_repo = WorkflowExecutionRepository(db)

    async def execute(
        self, ctx: RequestContext, workflow: Workflow, trigger_ctx: WorkflowTriggerContext
    ) -> Optional[WorkflowExecution]:
        """Main orchestrator execution loop."""
        # 1. Enforce workflow enable constraint
        if not workflow.enabled:
            raise ValidationException("Disabled workflows cannot be executed.")

        # 2. Check Idempotency Key deduplication
        idempotency_key = str(trigger_ctx.event_id)
        duplicate = await self.execution_repo.check_duplicate_execution(
            ctx.tenant_id, idempotency_key
        )
        if duplicate is not None:
            return duplicate  # Idempotent skip: already executed or running

        # 3. Create immutable Workflow snapshot
        snapshot = self._generate_snapshot(workflow)
        snapshot_str = json.dumps(snapshot, sort_keys=True)
        definition_hash = hashlib.sha256(snapshot_str.encode("utf-8")).hexdigest()

        # 4. Initialize execution run log (RUNNING status)
        actor_type = ActorType.SYSTEM
        if ctx.user:
            actor_type = ActorType.USER

        trigger_source = trigger_ctx.trigger_source or ("USER" if ctx.user else "SYSTEM")
        execution = WorkflowExecution(
            workflow_id=workflow.id,
            organization_id=ctx.tenant_id,
            entity_type=trigger_ctx.entity_type,
            entity_id=trigger_ctx.entity_id,
            status=WorkflowExecutionStatus.RUNNING,
            workflow_snapshot=snapshot,
            workflow_definition_hash=definition_hash,
            trigger_payload=trigger_ctx.payload,
            trigger_type=trigger_ctx.trigger_type,
            trigger_source=trigger_source,
            execution_mode=trigger_ctx.execution_mode,
            steps_total=len(workflow.actions),
            steps_success=0,
            steps_failed=0,
            steps_skipped=0,
            condition_duration_ms=0,
            action_duration_ms=0,
            idempotency_key=idempotency_key,
            request_id=ctx.request_id,
            triggered_by=actor_type,
            started_at=datetime.now(timezone.utc),
        )
        await self.execution_repo.create_execution(execution)
        # Flush to get the ID, commit in execution step boundaries
        await self.db.commit()

        # 5. Evaluate conditions (Condition Engine)
        cond_start = time.perf_counter_ns()
        conditions_passed, trace = WorkflowConditionEngine.evaluate(
            workflow.conditions, trigger_ctx.after
        )
        cond_end = time.perf_counter_ns()
        cond_duration = int((cond_end - cond_start) / 1_000_000)  # Convert to ms

        execution.condition_duration_ms = cond_duration
        execution.condition_trace = trace

        if not conditions_passed:
            # Mark skipped and terminate early
            execution.status = WorkflowExecutionStatus.SKIPPED
            execution.skipped_reason = "ConditionFalse"
            execution.steps_skipped = len(workflow.actions)
            execution.finished_at = datetime.now(timezone.utc)
            execution.duration_ms = int(
                (execution.finished_at - execution.started_at).total_seconds() * 1000
            )
            self.db.add(execution)
            await self.db.commit()
            
            # Eagerly query and return to prevent lazy loading issues
            stmt = (
                select(WorkflowExecution)
                .options(selectinload(WorkflowExecution.steps))
                .where(WorkflowExecution.id == execution.id)
            )
            res = await self.db.execute(stmt)
            return res.scalar_one()

        # 6. Execute actions sequentially (Action Engine)
        action_start = time.perf_counter_ns()
        execution_failed = False

        # Sort actions deterministic by order ASC
        sorted_actions = sorted(workflow.actions, key=lambda a: a.order)

        for index, action in enumerate(sorted_actions):
            step_order = index + 1
            step_start = time.perf_counter_ns()

            from app.services.workflow_action_engine import ACTION_HANDLERS
            handler = ACTION_HANDLERS.get(action.action_type)
            handler_name = handler.__class__.__name__ if handler else None

            step = WorkflowExecutionStep(
                execution_id=execution.id,
                step_order=step_order,
                action_type=action.action_type,
                handler_name=handler_name,
                input_json=sanitize_payload(action.configuration),
            )

            try:
                # Dispatch execution step to Action Engine
                output = await WorkflowActionEngine.execute_action(
                    ctx=ctx,
                    action_type=action.action_type,
                    configuration=action.configuration,
                    entity_id=trigger_ctx.entity_id,
                    db=self.db,
                )
                step.status = StepExecutionStatus.SUCCESS
                step.output_json = sanitize_payload(output)
                execution.steps_success += 1
            except Exception as e:
                # Mark step failed
                step.status = StepExecutionStatus.FAILED
                step.error_message = str(e)
                execution.steps_failed += 1
                execution_failed = True
            finally:
                step_end = time.perf_counter_ns()
                step.duration_ms = int((step_end - step_start) / 1_000_000)

                await self.execution_repo.create_execution_step(step)
                # Commit independently to fulfill Execution Step Independence Policy
                await self.db.commit()

            # Stop sequential executions if a step fails
            if execution_failed:
                # Rest of the steps are skipped
                skipped_count = len(sorted_actions) - step_order
                execution.steps_skipped = skipped_count
                execution.skipped_reason = "StepFailed"
                # Log the skipped steps in database
                for skipped_idx in range(step_order, len(sorted_actions)):
                    skipped_act = sorted_actions[skipped_idx]
                    skipped_h = ACTION_HANDLERS.get(skipped_act.action_type)
                    skipped_h_name = skipped_h.__class__.__name__ if skipped_h else None
                    
                    skipped_step = WorkflowExecutionStep(
                        execution_id=execution.id,
                        step_order=skipped_idx + 1,
                        action_type=skipped_act.action_type,
                        handler_name=skipped_h_name,
                        status=StepExecutionStatus.SKIPPED,
                        input_json=sanitize_payload(skipped_act.configuration),
                    )
                    await self.execution_repo.create_execution_step(skipped_step)
                    await self.db.commit()
                break

        action_end = time.perf_counter_ns()
        execution.action_duration_ms = int((action_end - action_start) / 1_000_000)

        # 7. Close and complete execution log
        execution.status = (
            WorkflowExecutionStatus.FAILED if execution_failed else WorkflowExecutionStatus.SUCCESS
        )
        execution.finished_at = datetime.now(timezone.utc)
        execution.duration_ms = int(
            (execution.finished_at - execution.started_at).total_seconds() * 1000
        )

        self.db.add(execution)
        await self.db.commit()

        # Eagerly load steps to prevent MissingGreenlet errors during serialization
        stmt = (
            select(WorkflowExecution)
            .options(selectinload(WorkflowExecution.steps))
            .where(WorkflowExecution.id == execution.id)
        )
        res = await self.db.execute(stmt)
        return res.scalar_one()

    def _generate_snapshot(self, workflow: Workflow) -> dict[str, Any]:
        """Builds a JSON-serializable snapshot dict of the workflow rule."""
        return {
            "workflow": {
                "id": str(workflow.id),
                "name": workflow.name,
                "trigger_type": workflow.trigger_type.value,
                "trigger_filter": workflow.trigger_filter,
                "retry_policy": workflow.retry_policy,
            },
            "conditions": [
                {
                    "field": c.field,
                    "operator": c.operator.value,
                    "value": c.value,
                    "value_type": c.value_type.value,
                    "group_id": c.group_id,
                    "logical_operator": c.logical_operator,
                    "order": c.order,
                }
                for c in workflow.conditions
            ],
            "actions": [
                {
                    "action_type": a.action_type.value,
                    "configuration": a.configuration,
                    "retryable": a.retryable,
                    "max_retries": a.max_retries,
                    "execution_mode": a.execution_mode,
                    "order": a.order,
                }
                for a in workflow.actions
            ],
        }


def sanitize_payload(payload: Any, max_len: int = 8192) -> dict[str, Any]:
    """Safely sanitizes/truncates any step payload to protect database log boundaries."""
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        payload = {"data": payload}
        
    try:
        dumped = json.dumps(payload)
        if len(dumped) <= max_len:
            return payload
        return {
            "_truncated": True,
            "truncated_data": dumped[:max_len],
        }
    except Exception as e:
        return {"error": f"Failed to serialize payload: {e}"}
