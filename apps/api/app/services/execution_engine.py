import time
import json
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.ai_plan import AIPlan
from app.models.ai_action import AIAction
from app.models.ai_approval import AIApproval
from app.models.enums import PlannerState, AIActionType, AIActionStatus, AIApprovalStatus, AIProvider
from app.services.policy_engine import AIPolicyEngine, PolicyDecision
from app.services.tool_registry import ToolRegistry
from app.core.events import DomainEvent, get_event_publisher
from app.models.ai_agent import AIAgent, AIProviderConfig
from app.services.llm_provider_registry import LLMProviderRegistry


class ExecutionEngine:
    @classmethod
    async def publish_event(cls, ctx: RequestContext, event_name: str, payload: dict) -> None:
        """Publishes local domain events inside transaction."""
        event = DomainEvent(
            event_name=event_name,
            tenant_id=ctx.tenant_id,
            request_id=ctx.request_id,
            actor_id=ctx.user.id if ctx.user else None,
            payload=payload
        )
        try:
            await get_event_publisher().publish(event)
        except Exception as e:
            print(f"Failed to publish domain event {event_name}: {str(e)}")

    @classmethod
    async def initialize_actions(cls, db: AsyncSession, ctx: RequestContext, plan: AIPlan) -> list[AIAction]:
        """Converts structured plan JSON steps into PENDING AIAction models with sequence dependencies."""
        steps = plan.plan_json.get("steps", [])
        created_actions = []
        prev_action_id = None

        for step in steps:
            action_type_str = step.get("action", "COMPLETE").upper()
            try:
                action_type = AIActionType[action_type_str]
            except KeyError:
                action_type = AIActionType.COMPLETE

            tool_name = step.get("tool")
            # If action type is SEND_EMAIL / SEND_WHATSAPP, map to communication tool
            if action_type in (AIActionType.SEND_EMAIL, AIActionType.SEND_WHATSAPP):
                tool_name = "send_communication"
            elif action_type == AIActionType.CREATE_TASK:
                tool_name = "manage_task"
            elif action_type in (AIActionType.UPDATE_LEAD, AIActionType.CHANGE_STATUS):
                tool_name = "create_lead"

            # Construct action input template from description
            input_template = {
                "step_id": step.get("id"),
                "description": step.get("description", ""),
                "lead_id": str(plan.lead_id) if plan.lead_id else None
            }

            action = AIAction(
                plan_id=plan.id,
                depends_on_action_id=prev_action_id,
                action_type=action_type,
                tool_name=tool_name,
                status=AIActionStatus.PENDING,
                input_json=input_template,
                attempt_count=1,
                max_attempts=3
            )
            db.add(action)
            await db.flush()
            
            created_actions.append(action)
            prev_action_id = action.id

        plan.status = PlannerState.EXECUTING
        await db.flush()

        await cls.publish_event(ctx, "ai.plan.created", {
            "plan_id": str(plan.id),
            "goal": plan.goal,
            "steps_count": len(created_actions)
        })

        return created_actions

    @classmethod
    async def execute_plan(cls, db: AsyncSession, ctx: RequestContext, plan_id: uuid.UUID) -> AIPlan:
        """Executes next pending actions in the plan queue sequentially, validating safety policies."""
        plan = await db.get(AIPlan, plan_id)
        if not plan or plan.organization_id != ctx.tenant_id:
            raise ValueError("Plan not found or inaccessible.")

        # 1. Initialize actions if they don't exist
        stmt = select(AIAction).where(AIAction.plan_id == plan.id).order_by(AIAction.created_at.asc())
        res = await db.execute(stmt)
        actions = list(res.scalars().all())
        if not actions:
            actions = await cls.initialize_actions(db, ctx, plan)

        # 2. Iterate actions sequentially
        for action in actions:
            if action.status == AIActionStatus.SUCCESS:
                continue

            # Skip action if dependency failed or was rejected
            if action.depends_on_action_id:
                dep_action = await db.get(AIAction, action.depends_on_action_id)
                if dep_action and dep_action.status in (AIActionStatus.FAILED, AIActionStatus.REJECTED):
                    action.status = AIActionStatus.FAILED
                    action.last_error = f"Dependency step {dep_action.id} was unsuccessful (Status: {dep_action.status.value})."
                    await db.flush()
                    continue

            # Handle manual approval resolution
            if action.status == AIActionStatus.WAITING_APPROVAL:
                approval_stmt = select(AIApproval).where(AIApproval.action_id == action.id).order_by(AIApproval.created_at.desc())
                approval_res = await db.execute(approval_stmt)
                approval = approval_res.scalar_one_or_none()
                if approval:
                    if approval.status == AIApprovalStatus.APPROVED:
                        action.status = AIActionStatus.PENDING # Allow re-execution
                        await db.flush()
                    elif approval.status == AIApprovalStatus.REJECTED:
                        action.status = AIActionStatus.REJECTED
                        plan.status = PlannerState.FAILED
                        await db.flush()
                        await cls.publish_event(ctx, "ai.action.failed", {
                            "plan_id": str(plan.id),
                            "action_id": str(action.id),
                            "reason": "Human approval was rejected."
                        })
                        await cls.publish_event(ctx, "ai.execution.completed", {
                            "plan_id": str(plan.id),
                            "status": plan.status.value
                        })
                        return plan
                    else:
                        # Still pending approval, halt execution
                        plan.status = PlannerState.WAITING_APPROVAL
                        await db.flush()
                        return plan
                else:
                    action.status = AIActionStatus.PENDING

            # Evaluate Policy Engine
            policy_res = await AIPolicyEngine.evaluate(
                db=db,
                ctx=ctx,
                agent_type=plan.agent_type,
                action_type=action.action_type,
                tool_name=action.tool_name,
                input_json=action.input_json,
                plan_id=plan.id
            )

            decision = policy_res.get("decision", PolicyDecision.ALLOW)
            if decision == PolicyDecision.DENY:
                action.status = AIActionStatus.FAILED
                action.last_error = f"Policy '{policy_res.get('policy')}' denied execution: {policy_res.get('reason')}"
                plan.status = PlannerState.FAILED
                await db.flush()
                await cls.publish_event(ctx, "ai.action.failed", {
                    "plan_id": str(plan.id),
                    "action_id": str(action.id),
                    "reason": action.last_error
                })
                await cls.publish_event(ctx, "ai.execution.completed", {
                    "plan_id": str(plan.id),
                    "status": plan.status.value
                })
                return plan

            elif decision == PolicyDecision.REQUIRE_APPROVAL:
                action.status = AIActionStatus.WAITING_APPROVAL
                plan.status = PlannerState.WAITING_APPROVAL
                
                approval = AIApproval(
                    action_id=action.id,
                    requested_to=ctx.user.id if ctx.user else None,
                    approval_type="MANAGER",
                    status=AIApprovalStatus.PENDING,
                    reason=f"Policy Check Requirement: [{policy_res.get('policy')}] - Risk: {policy_res.get('risk')} - {policy_res.get('reason')}"
                )
                db.add(approval)
                await db.flush()

                await cls.publish_event(ctx, "ai.approval.requested", {
                    "plan_id": str(plan.id),
                    "action_id": str(action.id),
                    "approval_id": str(approval.id),
                    "reason": approval.reason
                })
                return plan

            # ALLOW - Run Action Step
            action.status = AIActionStatus.RUNNING
            action.started_at = datetime.now(timezone.utc)
            await db.flush()

            await cls.publish_event(ctx, "ai.action.started", {
                "plan_id": str(plan.id),
                "action_id": str(action.id),
                "action_type": action.action_type.value
            })

            # Call LLM to compile actual tool arguments based on description
            compiled_args = await cls._generate_tool_args(db, ctx, plan, action)
            action.input_json = compiled_args

            start_time = time.time()
            try:
                # 3. Execute Tool Handler
                if action.tool_name:
                    output = await ToolRegistry.validate_and_execute(
                        action.tool_name,
                        compiled_args,
                        db,
                        ctx
                    )
                else:
                    output = {"status": "success", "info": "Action complete (no tool needed)."}

                action.status = AIActionStatus.SUCCESS
                action.output_json = output
                action.finished_at = datetime.now(timezone.utc)
                action.duration_ms = int((time.time() - start_time) * 1000)
                await db.flush()

                await cls.publish_event(ctx, "ai.action.completed", {
                    "plan_id": str(plan.id),
                    "action_id": str(action.id),
                    "status": "SUCCESS"
                })

            except Exception as ex:
                action.last_error = str(ex)
                action.finished_at = datetime.now(timezone.utc)
                action.duration_ms = int((time.time() - start_time) * 1000)
                
                if action.attempt_count < action.max_attempts:
                    action.attempt_count += 1
                    action.status = AIActionStatus.PENDING # Retry on next loop/execution call
                    await db.flush()
                    return await cls.execute_plan(db, ctx, plan.id)
                else:
                    action.status = AIActionStatus.FAILED
                    plan.status = PlannerState.FAILED
                    await db.flush()

                    await cls.publish_event(ctx, "ai.action.failed", {
                        "plan_id": str(plan.id),
                        "action_id": str(action.id),
                        "reason": str(ex)
                    })
                    await cls.publish_event(ctx, "ai.execution.completed", {
                        "plan_id": str(plan.id),
                        "status": plan.status.value
                    })
                    return plan

        # Check if all steps completed
        stmt = select(AIAction).where(AIAction.plan_id == plan.id)
        res = await db.execute(stmt)
        all_actions = res.scalars().all()
        if all(a.status == AIActionStatus.SUCCESS for a in all_actions):
            plan.status = PlannerState.COMPLETED
            await db.flush()
            await cls.publish_event(ctx, "ai.execution.completed", {
                "plan_id": str(plan.id),
                "status": "COMPLETED"
            })

        return plan

    @classmethod
    async def _generate_tool_args(cls, db: AsyncSession, ctx: RequestContext, plan: AIPlan, action: AIAction) -> dict:
        """Invokes standard LLM provider to render structured parameters matching the step tool definition."""
        # Check fallback defaults
        lead_id_str = str(plan.lead_id) if plan.lead_id else ""
        step_desc = action.input_json.get("description", "")

        # Fallback quick argument parser
        if action.action_type == AIActionType.ANALYZE_LEAD:
            return {"action": "analyze_lead", "lead_id": lead_id_str}
        
        elif action.action_type in (AIActionType.SEND_EMAIL, AIActionType.SEND_WHATSAPP):
            # Resolve lead email/phone
            from app.models.lead import Lead
            lead = await db.get(Lead, plan.lead_id) if plan.lead_id else None
            email = lead.email if lead else "lead@example.com"
            phone = lead.phone if lead else "+1234567890"

            channel_str = "EMAIL" if action.action_type == AIActionType.SEND_EMAIL else "WHATSAPP"
            
            # Simple heuristics for mail generation or simple LLM call
            subject_str = f"Following up from HireAI"
            body_str = f"Hi {lead.first_name if lead else 'there'},\n\nWe wanted to reach out regarding our initial demo session. Let us know if you have time next week."
            
            # Generate body via LLM if provider keys are active
            agent_stmt = select(AIAgent).where(AIAgent.organization_id == ctx.tenant_id, AIAgent.enabled == True, AIAgent.deleted_at.is_(None)).limit(1)
            agent = (await db.execute(agent_stmt)).scalar_one_or_none()
            if agent:
                provider_type = agent.provider
                model_name = agent.model
                
                system_prompt = (
                    "You are a sales communication copywriting helper. Output a JSON object with this structure:\n"
                    "{\n"
                    '  "subject": "Email subject (optional for whatsapp)",\n'
                    '  "body": "Message content body"\n'
                    "}\n"
                    "Strictly output only JSON, no markdown formatting."
                )
                user_prompt = f"Lead details: {lead.first_name if lead else ''} in status {lead.status if lead else ''}. Step instruction: {step_desc}. Generate professional content."
                try:
                    provider = LLMProviderRegistry.get_provider(provider_type)
                    res = await provider.generate([{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], model=model_name)
                    data = json.loads(res.get("content", "{}").strip())
                    if "body" in data:
                        body_str = data["body"]
                    if "subject" in data:
                        subject_str = data["subject"]
                except Exception:
                    pass

            return {
                "action": "send_communication" if action.action_type == AIActionType.SEND_EMAIL else "send_whatsapp",
                "channel": channel_str,
                "recipient_type": "LEAD",
                "lead_id": lead_id_str,
                "subject": subject_str,
                "body": body_str
            }

        elif action.action_type == AIActionType.CREATE_TASK:
            return {
                "action": "create_task",
                "task_data": {
                    "lead_id": lead_id_str,
                    "title": f"Follow-up: {plan.goal[:40]}",
                    "description": step_desc,
                    "type": "FOLLOW_UP",
                    "priority": "MEDIUM",
                    "due_at": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
                }
            }

        elif action.action_type in (AIActionType.UPDATE_LEAD, AIActionType.CHANGE_STATUS):
            # Determine status transitions based on lead stage
            from app.models.lead import Lead
            lead = await db.get(Lead, plan.lead_id) if plan.lead_id else None
            next_status = "CONTACTED"
            if lead:
                if lead.status.value if hasattr(lead.status, 'value') else lead.status == "NEW":
                    next_status = "CONTACTED"
                elif lead.status.value if hasattr(lead.status, 'value') else lead.status == "CONTACTED":
                    next_status = "MEETING_SCHEDULED"
            
            return {
                "action": "update_lead",
                "lead_id": lead_id_str,
                "lead_data": {
                    "status": next_status,
                    "version": lead.version if lead else 1
                }
            }

        return {"action": "wait", "duration_minutes": 60}
