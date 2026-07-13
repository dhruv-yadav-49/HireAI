import uuid
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.exceptions import ValidationException, ConcurrentUpdateException
from app.models.ai_agent import AIAgent, AIProviderConfig
from app.models.ai_conversation import AIConversation
from app.models.ai_message import AIMessage
from app.models.ai_prompt import AIPrompt
from app.models.ai_tool_execution import AIToolExecution
from app.schemas.ai import (
    AIAgentCreateRequest,
    AIAgentUpdateRequest,
    AIPromptCreateRequest,
    AIPromptUpdateRequest,
    AIProviderConfigCreateRequest,
    AIProviderConfigUpdateRequest,
    AIChatRequest,
    AIChatResponse,
    AIMessageResponse,
    AIToolExecutionResponse
)
from app.services.ai_runtime import AIRuntime
from app.services.llm_provider_registry import LLMProviderRegistry


class AIService:
    """Orchestration service managing CRUD configurations and run execution entries for AI domains."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── AI Provider Configuration CRUD ──────────────────────────────────────────

    async def create_provider_config(self, ctx: RequestContext, data: AIProviderConfigCreateRequest) -> AIProviderConfig:
        # If is_default is True, clear existing defaults for this provider
        if data.is_default:
            await self._clear_default_provider(ctx, data.provider)

        config = AIProviderConfig(
            organization_id=ctx.tenant_id,
            provider=data.provider,
            display_name=data.display_name,
            credentials_json=data.credentials_json,
            configuration_json=data.configuration_json,
            is_default=data.is_default,
            enabled=data.enabled,
            health_status="UNKNOWN"
        )
        self.db.add(config)
        await self.db.commit()
        await self.db.refresh(config)
        return config

    async def get_provider_config(self, ctx: RequestContext, config_id: uuid.UUID) -> AIProviderConfig:
        config = await self.db.get(AIProviderConfig, config_id)
        if not config or config.organization_id != ctx.tenant_id:
            raise ValidationException("AI Provider Configuration not found.")
        return config

    async def list_provider_configs(self, ctx: RequestContext) -> list[AIProviderConfig]:
        query = select(AIProviderConfig).where(AIProviderConfig.organization_id == ctx.tenant_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_provider_config(self, ctx: RequestContext, config_id: uuid.UUID, data: AIProviderConfigUpdateRequest) -> AIProviderConfig:
        config = await self.get_provider_config(ctx, config_id)

        if data.display_name is not None:
            config.display_name = data.display_name
        if data.credentials_json is not None:
            config.credentials_json = data.credentials_json
        if data.configuration_json is not None:
            config.configuration_json = data.configuration_json
        if data.enabled is not None:
            config.enabled = data.enabled
        if data.is_default is not None:
            if data.is_default and not config.is_default:
                await self._clear_default_provider(ctx, config.provider)
            config.is_default = data.is_default

        await self.db.commit()
        await self.db.refresh(config)
        return config

    async def test_provider_health(self, ctx: RequestContext, config_id: uuid.UUID) -> str:
        config = await self.get_provider_config(ctx, config_id)
        provider_impl = LLMProviderRegistry.get_provider(config.provider)
        
        # Determine target test model
        model = config.configuration_json.get("default_model", "mock-model")
        
        healthy = await provider_impl.health_check(model, config.credentials_json)
        config.health_status = "HEALTHY" if healthy else "UNHEALTHY"
        await self.db.commit()
        return config.health_status

    async def _clear_default_provider(self, ctx: RequestContext, provider: str) -> None:
        query = select(AIProviderConfig).where(
            and_(
                AIProviderConfig.organization_id == ctx.tenant_id,
                AIProviderConfig.provider == provider,
                AIProviderConfig.is_default == True
            )
        )
        result = await self.db.execute(query)
        for config in result.scalars().all():
            config.is_default = False

    # ── AI Prompt Templates CRUD ───────────────────────────────────────────────────

    async def create_prompt(self, ctx: RequestContext, data: AIPromptCreateRequest) -> AIPrompt:
        prompt = AIPrompt(
            organization_id=ctx.tenant_id,
            name=data.name,
            prompt_type=data.prompt_type,
            content=data.content,
            variables_json=data.variables_json,
            version=1,
            enabled=data.enabled
        )
        self.db.add(prompt)
        await self.db.commit()
        await self.db.refresh(prompt)
        return prompt

    async def get_prompt(self, ctx: RequestContext, prompt_id: uuid.UUID) -> AIPrompt:
        prompt = await self.db.get(AIPrompt, prompt_id)
        if not prompt or prompt.organization_id != ctx.tenant_id or prompt.deleted_at is not None:
            raise ValidationException("AI Prompt template not found.")
        return prompt

    async def list_prompts(self, ctx: RequestContext) -> list[AIPrompt]:
        query = select(AIPrompt).where(
            and_(AIPrompt.organization_id == ctx.tenant_id, AIPrompt.deleted_at == None)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_prompt(self, ctx: RequestContext, prompt_id: uuid.UUID, data: AIPromptUpdateRequest, current_version: int) -> AIPrompt:
        prompt = await self.get_prompt(ctx, prompt_id)

        # Optimistic Locking check
        if prompt.version != current_version:
            raise ConcurrentUpdateException("AI Prompt version mismatch. The template has been updated by another action.")

        if data.name is not None:
            prompt.name = data.name
        if data.prompt_type is not None:
            prompt.prompt_type = data.prompt_type
        if data.content is not None:
            prompt.content = data.content
            prompt.version += 1
        if data.variables_json is not None:
            prompt.variables_json = data.variables_json
        if data.enabled is not None:
            prompt.enabled = data.enabled

        await self.db.commit()
        await self.db.refresh(prompt)
        return prompt

    # ── AI Agent CRUD ─────────────────────────────────────────────────────────────

    async def create_agent(self, ctx: RequestContext, data: AIAgentCreateRequest) -> AIAgent:
        agent = AIAgent(
            organization_id=ctx.tenant_id,
            name=data.name,
            description=data.description,
            role=data.role,
            system_prompt=data.system_prompt,
            default_prompt_id=data.default_prompt_id,
            provider_config_id=data.provider_config_id,
            provider=data.provider,
            model=data.model,
            temperature=data.temperature,
            max_tokens=data.max_tokens,
            supports_tools=data.supports_tools,
            supports_streaming=data.supports_streaming,
            supports_memory=data.supports_memory,
            enabled=data.enabled,
            version=1,
            created_by=ctx.user.id if ctx.user else uuid.uuid4(),
            updated_by=ctx.user.id if ctx.user else uuid.uuid4()
        )
        self.db.add(agent)
        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def get_agent(self, ctx: RequestContext, agent_id: uuid.UUID) -> AIAgent:
        agent = await self.db.get(AIAgent, agent_id)
        if not agent or agent.organization_id != ctx.tenant_id or agent.deleted_at is not None:
            raise ValidationException("AI Agent settings not found.")
        return agent

    async def list_agents(self, ctx: RequestContext) -> list[AIAgent]:
        query = select(AIAgent).where(
            and_(AIAgent.organization_id == ctx.tenant_id, AIAgent.deleted_at == None)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_agent(self, ctx: RequestContext, agent_id: uuid.UUID, data: AIAgentUpdateRequest, current_version: int) -> AIAgent:
        agent = await self.get_agent(ctx, agent_id)

        # Optimistic Locking check
        if agent.version != current_version:
            raise ConcurrentUpdateException("AI Agent version mismatch. Settings have been updated by another action.")

        if data.name is not None:
            agent.name = data.name
        if data.description is not None:
            agent.description = data.description
        if data.role is not None:
            agent.role = data.role
        if data.system_prompt is not None:
            agent.system_prompt = data.system_prompt
            agent.version += 1
        if data.default_prompt_id is not None:
            agent.default_prompt_id = data.default_prompt_id
        if data.provider_config_id is not None:
            agent.provider_config_id = data.provider_config_id
        if data.provider is not None:
            agent.provider = data.provider
        if data.model is not None:
            agent.model = data.model
        if data.temperature is not None:
            agent.temperature = data.temperature
        if data.max_tokens is not None:
            agent.max_tokens = data.max_tokens
        if data.supports_tools is not None:
            agent.supports_tools = data.supports_tools
        if data.supports_streaming is not None:
            agent.supports_streaming = data.supports_streaming
        if data.supports_memory is not None:
            agent.supports_memory = data.supports_memory
        if data.enabled is not None:
            agent.enabled = data.enabled

        agent.updated_by = ctx.user.id if ctx.user else agent.updated_by
        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def delete_agent(self, ctx: RequestContext, agent_id: uuid.UUID) -> None:
        agent = await self.get_agent(ctx, agent_id)
        # Soft delete
        agent.soft_delete()
        await self.db.commit()

    # ── Chat Execution Orchestrator ────────────────────────────────────────────

    async def chat(self, ctx: RequestContext, req: AIChatRequest) -> AIChatResponse:
        conversation, message, tools = await AIRuntime.execute_run(
            db=self.db,
            ctx=ctx,
            agent_id=req.agent_id,
            user_message=req.message,
            conversation_id=req.conversation_id,
            lead_id=req.lead_id
        )
        
        # Serialize tool executions to schemas
        tool_responses = []
        for t in tools:
            tool_responses.append(AIToolExecutionResponse.model_validate(t))

        await self.db.commit()
        return AIChatResponse(
            conversation_id=conversation.id,
            agent_id=conversation.agent_id,
            status=conversation.status,
            runtime_state=conversation.runtime_state,
            message=AIMessageResponse.model_validate(message),
            tool_executions=tool_responses
        )

    # ── History & Auditing Logs ───────────────────────────────────────────────

    async def list_conversations(self, ctx: RequestContext) -> list[AIConversation]:
        query = select(AIConversation).where(AIConversation.organization_id == ctx.tenant_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_conversation(self, ctx: RequestContext, conversation_id: uuid.UUID) -> AIConversation:
        conversation = await self.db.get(AIConversation, conversation_id)
        if not conversation or conversation.organization_id != ctx.tenant_id:
            raise ValidationException("AI Conversation session not found.")
        return conversation

    async def list_conversation_messages(self, ctx: RequestContext, conversation_id: uuid.UUID) -> list[AIMessage]:
        # Validate conversation access first
        await self.get_conversation(ctx, conversation_id)
        
        query = select(AIMessage).where(AIMessage.conversation_id == conversation_id).order_by(AIMessage.message_index)
        result = await self.db.execute(query)
        return list(result.scalars().all())
