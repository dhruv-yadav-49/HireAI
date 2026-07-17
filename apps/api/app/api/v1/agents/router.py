import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.context import RequestContext
from app.core.dependencies import get_current_context
from app.schemas.orchestration import (
    AIAgentSessionCreateRequest,
    AIAgentSessionResponse,
    AIAgentTaskResponse,
    AIAgentMessageResponse,
    AIAgentWorkflowResponse,
    AIAgentDelegationRequest,
    AIAgentHandoffRequest
)
from app.services.orchestrator import Orchestrator

router = APIRouter(prefix="/agents", tags=["Multi-Agent Orchestration"])


@router.post("/session", response_model=AIAgentSessionResponse)
async def create_session(
    body: AIAgentSessionCreateRequest,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    orchestrator = Orchestrator(db)
    try:
        session = await orchestrator.create_session(
            ctx,
            initiator_agent=body.initiator_agent,
            conversation_id=body.conversation_id
        )
        await db.commit()
        return session
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/delegate")
async def delegate_task(
    body: AIAgentDelegationRequest,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    orchestrator = Orchestrator(db)
    try:
        res = await orchestrator.delegate_task(
            ctx,
            session_id=body.session_id,
            goal=body.goal
        )
        await db.commit()
        return {
            "task": AIAgentTaskResponse.model_validate(res["task"]),
            "delegation_metrics": res["delegation_metrics"]
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/handoff", response_model=AIAgentMessageResponse)
async def perform_handoff(
    body: AIAgentHandoffRequest,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    orchestrator = Orchestrator(db)
    try:
        msg = await orchestrator.perform_handoff(
            ctx,
            session_id=body.session_id,
            from_agent=body.from_agent,
            to_agent=body.to_agent,
            content=body.content,
            correlation_id=body.correlation_id,
            causation_id=body.causation_id
        )
        await db.commit()
        return msg
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tasks")
async def list_tasks(
    session_id: Optional[uuid.UUID] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    orchestrator = Orchestrator(db)
    tasks, total = await orchestrator.repo.list_tasks(
        ctx, session_id=session_id, page=page, page_size=page_size
    )
    return {
        "items": [AIAgentTaskResponse.model_validate(t) for t in tasks],
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.get("/messages")
async def list_messages(
    session_id: Optional[uuid.UUID] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    orchestrator = Orchestrator(db)
    messages, total = await orchestrator.repo.list_messages(
        ctx, session_id=session_id, page=page, page_size=page_size
    )
    return {
        "items": [AIAgentMessageResponse.model_validate(m) for m in messages],
        "total": total,
        "page": page,
        "page_size": page_size
    }


@router.get("/workflows")
async def list_workflows(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context)
):
    orchestrator = Orchestrator(db)
    workflows, total = await orchestrator.repo.list_workflows(
        ctx, page=page, page_size=page_size
    )
    return {
        "items": [AIAgentWorkflowResponse.model_validate(w) for w in workflows],
        "total": total,
        "page": page,
        "page_size": page_size
    }
