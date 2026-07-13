import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_request_context
from app.core.context import RequestContext
from app.db.session import get_db
from app.schemas.ai import (
    AIAgentCreateRequest,
    AIAgentUpdateRequest,
    AIAgentResponse,
    AIPromptCreateRequest,
    AIPromptUpdateRequest,
    AIPromptResponse,
    AIProviderConfigCreateRequest,
    AIProviderConfigUpdateRequest,
    AIProviderConfigResponse,
    AIChatRequest,
    AIChatResponse,
    AIConversationResponse,
    AIMessageResponse
)
from app.services.ai_service import AIService

router = APIRouter(prefix="/ai", tags=["ai"])


# ── AI Provider Configuration Endpoints ─────────────────────────────────────

@router.post(
    "/provider-configs",
    response_model=AIProviderConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create AI provider config",
)
async def create_provider_config(
    data: AIProviderConfigCreateRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> AIProviderConfigResponse:
    service = AIService(db)
    config = await service.create_provider_config(ctx, data)
    return AIProviderConfigResponse.model_validate(config)


@router.get(
    "/provider-configs",
    response_model=list[AIProviderConfigResponse],
    summary="List AI provider configs",
)
async def list_provider_configs(
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> list[AIProviderConfigResponse]:
    service = AIService(db)
    configs = await service.list_provider_configs(ctx)
    return [AIProviderConfigResponse.model_validate(c) for c in configs]


@router.get(
    "/provider-configs/{id}",
    response_model=AIProviderConfigResponse,
    summary="Get AI provider config details",
)
async def get_provider_config(
    id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> AIProviderConfigResponse:
    service = AIService(db)
    config = await service.get_provider_config(ctx, id)
    return AIProviderConfigResponse.model_validate(config)


@router.patch(
    "/provider-configs/{id}",
    response_model=AIProviderConfigResponse,
    summary="Update AI provider config",
)
async def update_provider_config(
    id: uuid.UUID,
    data: AIProviderConfigUpdateRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> AIProviderConfigResponse:
    service = AIService(db)
    config = await service.update_provider_config(ctx, id, data)
    return AIProviderConfigResponse.model_validate(config)


@router.post(
    "/provider-configs/{id}/test",
    summary="Test AI provider credentials health status",
)
async def test_provider_health(
    id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    service = AIService(db)
    health_status = await service.test_provider_health(ctx, id)
    return {"health_status": health_status}


# ── AI Prompt Templates Endpoints ───────────────────────────────────────────

@router.post(
    "/prompts",
    response_model=AIPromptResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create AI prompt template",
)
async def create_prompt(
    data: AIPromptCreateRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> AIPromptResponse:
    service = AIService(db)
    prompt = await service.create_prompt(ctx, data)
    return AIPromptResponse.model_validate(prompt)


@router.get(
    "/prompts",
    response_model=list[AIPromptResponse],
    summary="List active AI prompt templates",
)
async def list_prompts(
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> list[AIPromptResponse]:
    service = AIService(db)
    prompts = await service.list_prompts(ctx)
    return [AIPromptResponse.model_validate(p) for p in prompts]


@router.get(
    "/prompts/{id}",
    response_model=AIPromptResponse,
    summary="Get AI prompt template details",
)
async def get_prompt(
    id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> AIPromptResponse:
    service = AIService(db)
    prompt = await service.get_prompt(ctx, id)
    return AIPromptResponse.model_validate(prompt)


@router.patch(
    "/prompts/{id}",
    response_model=AIPromptResponse,
    summary="Update AI prompt template details",
)
async def update_prompt(
    id: uuid.UUID,
    data: AIPromptUpdateRequest,
    version: int = Query(..., description="Current version of the prompt for optimistic locking check"),
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> AIPromptResponse:
    service = AIService(db)
    prompt = await service.update_prompt(ctx, id, data, current_version=version)
    return AIPromptResponse.model_validate(prompt)


# ── AI Agents Endpoints ───────────────────────────────────────────────────────

@router.post(
    "/agents",
    response_model=AIAgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create AI Agent settings",
)
async def create_agent(
    data: AIAgentCreateRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> AIAgentResponse:
    service = AIService(db)
    agent = await service.create_agent(ctx, data)
    return AIAgentResponse.model_validate(agent)


@router.get(
    "/agents",
    response_model=list[AIAgentResponse],
    summary="List active AI Agents",
)
async def list_agents(
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> list[AIAgentResponse]:
    service = AIService(db)
    agents = await service.list_agents(ctx)
    return [AIAgentResponse.model_validate(a) for a in agents]


@router.get(
    "/agents/{id}",
    response_model=AIAgentResponse,
    summary="Get AI Agent detailed settings",
)
async def get_agent(
    id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> AIAgentResponse:
    service = AIService(db)
    agent = await service.get_agent(ctx, id)
    return AIAgentResponse.model_validate(agent)


@router.patch(
    "/agents/{id}",
    response_model=AIAgentResponse,
    summary="Update AI Agent settings",
)
async def update_agent(
    id: uuid.UUID,
    data: AIAgentUpdateRequest,
    version: int = Query(..., description="Current version of the agent for optimistic locking check"),
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> AIAgentResponse:
    service = AIService(db)
    agent = await service.update_agent(ctx, id, data, current_version=version)
    return AIAgentResponse.model_validate(agent)


@router.delete(
    "/agents/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete an AI Agent",
)
async def delete_agent(
    id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    service = AIService(db)
    await service.delete_agent(ctx, id)
    return None


# ── Chat Execution Endpoint ──────────────────────────────────────────────────

@router.post(
    "/chat",
    response_model=AIChatResponse,
    summary="Execute AI Chat session run",
)
async def chat(
    data: AIChatRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> AIChatResponse:
    service = AIService(db)
    return await service.chat(ctx, data)


# ── Conversations History & Messages Logs ───────────────────────────────────

@router.get(
    "/conversations",
    response_model=list[AIConversationResponse],
    summary="List conversation history logs",
)
async def list_conversations(
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> list[AIConversationResponse]:
    service = AIService(db)
    conversations = await service.list_conversations(ctx)
    return [AIConversationResponse.model_validate(c) for c in conversations]


@router.get(
    "/conversations/{id}",
    response_model=AIConversationResponse,
    summary="Get conversation session metrics details",
)
async def get_conversation(
    id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> AIConversationResponse:
    service = AIService(db)
    conversation = await service.get_conversation(ctx, id)
    return AIConversationResponse.model_validate(conversation)


@router.get(
    "/messages/{conversation_id}",
    response_model=list[AIMessageResponse],
    summary="Retrieve chronological messages history list",
)
async def list_conversation_messages(
    conversation_id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> list[AIMessageResponse]:
    service = AIService(db)
    messages = await service.list_conversation_messages(ctx, conversation_id)
    return [AIMessageResponse.model_validate(m) for m in messages]
