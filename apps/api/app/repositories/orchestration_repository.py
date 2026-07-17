import uuid
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.ai_agent_session import AIAgentSession
from app.models.ai_agent_task import AIAgentTask
from app.models.ai_agent_message import AIAgentMessage
from app.models.ai_agent_workflow import AIAgentWorkflow


class OrchestrationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_session(self, session: AIAgentSession) -> AIAgentSession:
        self.db.add(session)
        await self.db.flush()
        return session

    async def get_session_by_id(self, ctx: RequestContext, session_id: uuid.UUID) -> AIAgentSession | None:
        result = await self.db.execute(
            select(AIAgentSession).where(
                AIAgentSession.id == session_id,
                AIAgentSession.organization_id == ctx.tenant_id
            )
        )
        return result.scalar_one_or_none()

    async def update_session(self, session: AIAgentSession) -> AIAgentSession:
        self.db.add(session)
        await self.db.flush()
        return session

    async def create_task(self, task: AIAgentTask) -> AIAgentTask:
        self.db.add(task)
        await self.db.flush()
        return task

    async def get_task_by_id(self, ctx: RequestContext, task_id: uuid.UUID) -> AIAgentTask | None:
        result = await self.db.execute(
            select(AIAgentTask)
            .join(AIAgentSession, AIAgentTask.session_id == AIAgentSession.id)
            .where(
                AIAgentTask.id == task_id,
                AIAgentSession.organization_id == ctx.tenant_id
            )
        )
        return result.scalar_one_or_none()

    async def list_tasks(
        self,
        ctx: RequestContext,
        session_id: Optional[uuid.UUID] = None,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[list[AIAgentTask], int]:
        stmt = select(AIAgentTask).join(AIAgentSession, AIAgentTask.session_id == AIAgentSession.id).where(AIAgentSession.organization_id == ctx.tenant_id)
        if session_id is not None:
            stmt = stmt.where(AIAgentTask.session_id == session_id)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        stmt = stmt.order_by(AIAgentTask.created_at.asc()).offset(offset).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def create_message(self, message: AIAgentMessage) -> AIAgentMessage:
        self.db.add(message)
        await self.db.flush()
        return message

    async def list_messages(
        self,
        ctx: RequestContext,
        session_id: Optional[uuid.UUID] = None,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[list[AIAgentMessage], int]:
        stmt = select(AIAgentMessage).join(AIAgentSession, AIAgentMessage.session_id == AIAgentSession.id).where(AIAgentSession.organization_id == ctx.tenant_id)
        if session_id is not None:
            stmt = stmt.where(AIAgentMessage.session_id == session_id)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        stmt = stmt.order_by(AIAgentMessage.created_at.asc()).offset(offset).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def create_workflow(self, workflow: AIAgentWorkflow) -> AIAgentWorkflow:
        self.db.add(workflow)
        await self.db.flush()
        return workflow

    async def get_workflow_by_session_id(self, ctx: RequestContext, session_id: uuid.UUID) -> AIAgentWorkflow | None:
        result = await self.db.execute(
            select(AIAgentWorkflow)
            .join(AIAgentSession, AIAgentWorkflow.session_id == AIAgentSession.id)
            .where(
                AIAgentWorkflow.session_id == session_id,
                AIAgentSession.organization_id == ctx.tenant_id
            )
        )
        return result.scalar_one_or_none()

    async def list_workflows(
        self,
        ctx: RequestContext,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[list[AIAgentWorkflow], int]:
        stmt = select(AIAgentWorkflow).join(AIAgentSession, AIAgentWorkflow.session_id == AIAgentSession.id).where(AIAgentSession.organization_id == ctx.tenant_id)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        stmt = stmt.order_by(AIAgentWorkflow.created_at.desc()).offset(offset).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total
