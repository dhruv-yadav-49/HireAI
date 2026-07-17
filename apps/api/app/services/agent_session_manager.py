import json
import hashlib
import uuid
from typing import Optional, Any
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.ai_agent_session import AIAgentSession


class AgentSessionManager:
    @classmethod
    async def build_shared_context(
        cls,
        db: AsyncSession,
        ctx: RequestContext,
        lead_id: Optional[uuid.UUID] = None
    ) -> dict[str, Any]:
        """Queries CRM, tasks, and memory to generate a unified snapshot context."""
        context_payload = {
            "lead": None,
            "tasks": [],
            "memories": []
        }

        # 1. CRM Lead
        if lead_id:
            from app.models.lead import Lead
            lead = await db.get(Lead, lead_id)
            if lead and lead.organization_id == ctx.tenant_id:
                context_payload["lead"] = {
                    "id": str(lead.id),
                    "name": f"{lead.first_name or ''} {lead.last_name or ''}".strip() or lead.company_name or "Unknown",
                    "status": lead.status.value if hasattr(lead.status, 'value') else lead.status,
                    "estimated_value": float(lead.estimated_value or 0)
                }

                # 2. CRM Tasks
                from app.models.task import Task
                from sqlalchemy import select
                stmt = select(Task).where(Task.lead_id == lead_id)
                res = await db.execute(stmt)
                tasks = res.scalars().all()
                context_payload["tasks"] = [
                    {
                        "id": str(t.id),
                        "title": t.title,
                        "status": t.status.value if hasattr(t.status, 'value') else t.status
                    } for t in tasks
                ]

                # 3. Memories
                from app.services.memory_service import MemoryService
                memories = await MemoryService.get_active_memories(db, ctx.tenant_id, lead_id=lead_id)
                context_payload["memories"] = [
                    {
                        "id": str(m["id"]),
                        "content": m["content"],
                        "source": m["source"]
                    } for m in memories
                ]

        return context_payload

    @classmethod
    def compute_checksum(cls, context_payload: dict[str, Any]) -> str:
        """Returns stable checksum hash for context payload verification."""
        dumped = json.dumps(context_payload, sort_keys=True, default=str)
        return hashlib.sha256(dumped.encode()).hexdigest()

    @classmethod
    async def initialize_session_context(
        cls,
        db: AsyncSession,
        ctx: RequestContext,
        session: AIAgentSession,
        lead_id: Optional[uuid.UUID] = None
    ) -> None:
        """Saves initialized context version and checksum snapshot on session."""
        context_payload = await cls.build_shared_context(db, ctx, lead_id=lead_id)
        session.shared_context_json = context_payload
        session.shared_context_version = 1
        session.shared_context_checksum = cls.compute_checksum(context_payload)
        
        # Initialize timeline logs
        session.timeline_json = {
            "history": [
                {
                    "event": "created",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "actor_id": str(ctx.user.id) if ctx.user else None
                }
            ]
        }
