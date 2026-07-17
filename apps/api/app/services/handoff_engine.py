import uuid
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession


from app.models.ai_agent_session import AIAgentSession
from app.models.ai_agent_message import AIAgentMessage
from app.models.enums import AgentType, MessageType
from app.services.agent_session_manager import AgentSessionManager


class HandoffEngine:
    @classmethod
    async def perform_handoff(
        cls,
        db: AsyncSession,
        session: AIAgentSession,
        from_agent: AgentType,
        to_agent: AgentType,
        content: str,
        correlation_id: uuid.UUID,
        causation_id: Optional[uuid.UUID] = None
    ) -> AIAgentMessage:
        """Transfers execution trace bounds between agents, recording state transitions."""
        # 1. Update shared context version
        session.shared_context_version += 1
        session.shared_context_checksum = AgentSessionManager.compute_checksum(session.shared_context_json)

        # 2. Append handoff event to timeline history
        history = session.timeline_json.get("history", [])
        history.append({
            "event": "handoff",
            "from_agent": from_agent.value,
            "to_agent": to_agent.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": session.shared_context_version
        })
        session.timeline_json = {"history": history}

        # 3. Create Handoff Message
        message = AIAgentMessage(
            session_id=session.id,
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=MessageType.HANDOFF,
            content=content,
            correlation_id=correlation_id,
            causation_id=causation_id,
            metadata_json={
                "shared_context_version": session.shared_context_version,
                "shared_context_checksum": session.shared_context_checksum
            }
        )
        db.add(message)
        await db.flush()

        return message
