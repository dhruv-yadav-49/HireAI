import uuid
from typing import Any, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.ai_agent_session import AIAgentSession
from app.models.ai_agent_task import AIAgentTask
from app.models.ai_agent_message import AIAgentMessage
from app.models.ai_agent_workflow import AIAgentWorkflow
from app.models.enums import AgentType, SessionStatus, AgentTaskStatus, MessageType, CollaborationMode
from app.repositories.orchestration_repository import OrchestrationRepository
from app.services.agent_session_manager import AgentSessionManager
from app.services.delegation_engine import DelegationEngine
from app.services.handoff_engine import HandoffEngine
from app.services.conflict_resolver import ConflictResolver
from app.services.collaboration_engine import CollaborationEngine
from app.core.events import DomainEvent, get_event_publisher


class Orchestrator:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = OrchestrationRepository(db)

    async def publish_event(self, ctx: RequestContext, event_name: str, payload: dict) -> None:
        """Publishes local domain events inside transaction."""
        event = DomainEvent(
            event_name=event_name,
            tenant_id=ctx.tenant_id,
            request_id=ctx.request_id,
            actor_id=ctx.user.id if ctx.user else None,
            payload=payload
        )
        pub = get_event_publisher()
        await pub.publish(event)

    async def create_session(
        self,
        ctx: RequestContext,
        initiator_agent: AgentType,
        conversation_id: Optional[uuid.UUID] = None,
        lead_id: Optional[uuid.UUID] = None
    ) -> AIAgentSession:
        """Creates orchestrator collaborative session and sets up initial context."""
        session = AIAgentSession(
            organization_id=ctx.tenant_id,
            conversation_id=conversation_id,
            initiator_agent=initiator_agent,
            status=SessionStatus.ACTIVE
        )
        
        # Build shared context snapshot
        await AgentSessionManager.initialize_session_context(self.db, ctx, session, lead_id=lead_id)
        
        await self.repo.create_session(session)
        
        # Publish event
        await self.publish_event(ctx, "agent.session.created", {
            "session_id": str(session.id),
            "initiator_agent": initiator_agent.value,
            "shared_context_version": session.shared_context_version
        })
        
        return session

    async def delegate_task(
        self,
        ctx: RequestContext,
        session_id: uuid.UUID,
        goal: str,
        priority: str = "MEDIUM",
        parent_task_id: Optional[uuid.UUID] = None
    ) -> dict[str, Any]:
        """Runs the delegation engine scoring, creates the task, and updates the timeline."""
        session = await self.repo.get_session_by_id(ctx, session_id)
        if not session:
            raise ValueError("Session not found or unauthorized.")

        # Match goal to agent
        delegation_res = await DelegationEngine.delegate_goal(self.db, goal)
        assigned_agent = delegation_res["selected_agent"]

        task = AIAgentTask(
            session_id=session_id,
            assigned_agent=assigned_agent,
            goal=goal,
            status=AgentTaskStatus.CREATED,
            priority=priority,
            parent_task_id=parent_task_id
        )
        await self.repo.create_task(task)

        # Update session timeline
        history = session.timeline_json.get("history", [])
        history.append({
            "event": "delegated",
            "task_id": str(task.id),
            "assigned_agent": assigned_agent.value,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        session.timeline_json = {"history": history}
        await self.repo.update_session(session)

        # Publish event
        await self.publish_event(ctx, "agent.task.assigned", {
            "session_id": str(session_id),
            "task_id": str(task.id),
            "assigned_agent": assigned_agent.value
        })

        return {
            "task": task,
            "delegation_metrics": {
                "selected_agent": assigned_agent.value,
                "candidates": [
                    {
                        "agent_type": c["agent_type"].value,
                        "capability_score": c["capability_score"],
                        "confidence": c["confidence"]
                    } for c in delegation_res["candidates"]
                ]
            }
        }

    async def execute_tasks(
        self,
        ctx: RequestContext,
        session_id: uuid.UUID,
        tasks: list[AIAgentTask],
        run_func: Any,
        mode: CollaborationMode = CollaborationMode.SEQUENTIAL
    ) -> list[dict[str, Any]]:
        """Schedules and executes tasks based on mode."""
        session = await self.repo.get_session_by_id(ctx, session_id)
        if not session:
            raise ValueError("Session not found or unauthorized.")

        # Update timeline
        history = session.timeline_json.get("history", [])
        history.append({
            "event": "started",
            "mode": mode.value,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        session.timeline_json = {"history": history}
        await self.repo.update_session(session)

        # Publish task started events
        for t in tasks:
            await self.publish_event(ctx, "agent.task.started", {
                "session_id": str(session_id),
                "task_id": str(t.id),
                "agent_type": t.assigned_agent.value
            })

        if mode == CollaborationMode.PARALLEL:
            results = await CollaborationEngine.execute_parallel_graph(self.db, session_id, tasks, run_func)
        else:
            results = await CollaborationEngine.execute_sequential_graph(self.db, session_id, tasks, run_func)

        # Publish task completed events
        for t in tasks:
            await self.publish_event(ctx, "agent.task.completed", {
                "session_id": str(session_id),
                "task_id": str(t.id),
                "status": t.status.value
            })

        # Append complete event to timeline
        history = session.timeline_json.get("history", [])
        history.append({
            "event": "completed",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        session.timeline_json = {"history": history}
        
        # Update session status if all completed
        all_success = all(t.status == AgentTaskStatus.COMPLETED for t in tasks)
        if all_success:
            session.status = SessionStatus.COMPLETED
            session.completed_at = datetime.now(timezone.utc)
            await self.publish_event(ctx, "agent.workflow.completed", {
                "session_id": str(session_id),
                "status": "COMPLETED"
            })
        else:
            session.status = SessionStatus.FAILED
            session.completed_at = datetime.now(timezone.utc)
            await self.publish_event(ctx, "agent.workflow.completed", {
                "session_id": str(session_id),
                "status": "FAILED"
            })

        await self.repo.update_session(session)
        return results

    async def perform_handoff(
        self,
        ctx: RequestContext,
        session_id: uuid.UUID,
        from_agent: AgentType,
        to_agent: AgentType,
        content: str,
        correlation_id: uuid.UUID,
        causation_id: Optional[uuid.UUID] = None
    ) -> AIAgentMessage:
        """Invokes the HandoffEngine to safely transfer execution contexts."""
        session = await self.repo.get_session_by_id(ctx, session_id)
        if not session:
            raise ValueError("Session not found or unauthorized.")

        msg = await HandoffEngine.perform_handoff(
            self.db, session, from_agent, to_agent, content, correlation_id, causation_id
        )

        await self.publish_event(ctx, "agent.handoff.completed", {
            "session_id": str(session_id),
            "from_agent": from_agent.value,
            "to_agent": to_agent.value,
            "shared_context_version": session.shared_context_version
        })

        return msg

    async def send_message(
        self,
        ctx: RequestContext,
        session_id: uuid.UUID,
        from_agent: AgentType,
        to_agent: AgentType,
        message_type: MessageType,
        content: str,
        correlation_id: uuid.UUID,
        causation_id: Optional[uuid.UUID] = None,
        metadata_json: Optional[dict] = None
    ) -> AIAgentMessage:
        """Sends and registers inter-agent messaging."""
        session = await self.repo.get_session_by_id(ctx, session_id)
        if not session:
            raise ValueError("Session not found or unauthorized.")

        msg = AIAgentMessage(
            session_id=session_id,
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            content=content,
            correlation_id=correlation_id,
            causation_id=causation_id,
            metadata_json=metadata_json or {}
        )
        await self.repo.create_message(msg)

        await self.publish_event(ctx, "agent.message.sent", {
            "session_id": str(session_id),
            "message_id": str(msg.id),
            "from_agent": from_agent.value,
            "to_agent": to_agent.value,
            "message_type": message_type.value
        })

        return msg

    async def resolve_disputes(
        self,
        ctx: RequestContext,
        recommendations: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Invokes ConflictResolver to deterministically resolve conflicts."""
        res = ConflictResolver.resolve_conflict(recommendations)
        
        await self.publish_event(ctx, "agent.conflict.resolved", {
            "winner": res["winner"]["agent_type"].value if "winner" in res and "agent_type" in res["winner"] else None
        })

        return res
