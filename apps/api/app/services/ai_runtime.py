import uuid
import json
import time
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.core.events import DomainEvent, get_event_publisher
from app.core.exceptions import ValidationException
from app.models.enums import AIRuntimeState, ConversationStatus, MessageRole, ToolExecutionStatus, AIProvider, EmbeddingProvider
from app.models.ai_agent import AIAgent, AIProviderConfig
from app.models.ai_conversation import AIConversation
from app.models.ai_message import AIMessage, AITokenUsage
from app.models.ai_prompt import AIPrompt, AIPromptExecution
from app.models.ai_tool_execution import AIToolExecution
from app.services.prompt_engine import PromptEngine
from app.services.llm_provider_registry import LLMProviderRegistry
from app.services.tool_registry import ToolRegistry
from app.services.retrieval_service import RetrievalService
from app.services.context_builder import ContextBuilder
from app.services.memory_service import MemoryService
from app.services.trace_collector import TraceCollector
from app.services.metric_aggregator import MetricAggregator
from app.models.enums import TraceStatus, AgentType, TraceSamplingMode


class AIRuntime:
    """The core execution engine running the prompt-to-response generation state machine."""

    @classmethod
    async def execute_run(
        self,
        db: AsyncSession,
        ctx: RequestContext,
        agent_id: uuid.UUID,
        user_message: str,
        conversation_id: Optional[uuid.UUID] = None,
        lead_id: Optional[uuid.UUID] = None,
        request_id: Optional[uuid.UUID] = None
    ) -> tuple[AIConversation, AIMessage, list[AIToolExecution]]:
        """Orchestrates loading settings, compiling prompts, fetching history logs, and running LLM cycles."""
        
        # 1. Load Agent Config
        agent = await db.get(AIAgent, agent_id)
        if not agent or agent.organization_id != ctx.tenant_id or agent.deleted_at is not None:
            raise ValidationException("AI Agent not found or inaccessible.")
        if not agent.enabled:
            raise ValidationException("The selected AI Agent is currently disabled.")

        # Resolve provider configuration details
        credentials = {}
        if agent.provider_config_id:
            config = await db.get(AIProviderConfig, agent.provider_config_id)
            if config and config.enabled:
                credentials = config.credentials_json

        # 2. Get or Create Conversation Session
        if conversation_id:
            conversation = await db.get(AIConversation, conversation_id)
            if not conversation or conversation.organization_id != ctx.tenant_id:
                raise ValidationException("AI Conversation session not found.")
            conversation.tool_iterations = 0  # reset for this run loop
        else:
            conversation = AIConversation(
                organization_id=ctx.tenant_id,
                agent_id=agent.id,
                lead_id=lead_id,
                user_id=ctx.user.id if ctx.user else None,
                status=ConversationStatus.ACTIVE,
                runtime_state=AIRuntimeState.IDLE,
                agent_snapshot={
                    "name": agent.name,
                    "role": agent.role,
                    "system_prompt": agent.system_prompt,
                    "provider": agent.provider,
                    "model": agent.model,
                    "temperature": agent.temperature,
                    "max_tokens": agent.max_tokens,
                },
                agent_version=agent.version,
                provider=agent.provider,
                model=agent.model,
                temperature=agent.temperature,
                max_tokens=agent.max_tokens,
                tool_iterations=0,
                max_tool_iterations=5,
                runtime_metrics={}
            )
            db.add(conversation)
            await db.flush()

            # Publish conversation started event
            await self._publish_event(ctx, "ai.conversation.started", conversation.id, {
                "agent_id": str(agent.id),
                "model": agent.model
            }, request_id)

        # 3. Transition to PROMPT_BUILD
        conversation.runtime_state = AIRuntimeState.PROMPT_BUILD
        await db.flush()

        # ── OBSERVABILITY: Start execution trace (ADR-016 — passive, non-blocking) ──
        exec_trace = await TraceCollector.start_execution(
            db=db,
            org_id=ctx.tenant_id,
            agent_type=AgentType.SALES,   # default; callers may override via subclass
            conversation_id=conversation.id,
            correlation_id=request_id if isinstance(request_id, uuid.UUID) else None,
            component="AIRuntime"
        )

        # ── RETRIEVAL INDEPENDENCE PIPELINE ──
        # Runtime calls RetrievalService exclusively to fetch context matching the user query
        retrieved_results = await RetrievalService.retrieve(
            db=db,
            org_id=ctx.tenant_id,
            query=user_message,
            conversation_id=conversation.id,
            lead_id=lead_id,
            user_id=conversation.user_id,
            provider=EmbeddingProvider.MOCK, # default embedding schema mapping
            limit=8
        )

        # Fetch sliding history messages (Last 20 messages)
        query_history = await db.execute(
            select(AIMessage)
            .where(AIMessage.conversation_id == conversation.id)
            .order_by(desc(AIMessage.message_index))
            .limit(20)
        )
        history_msgs = list(reversed(query_history.scalars().all()))
        history_payload = [{"role": m.role.lower(), "content": m.content} for m in history_msgs]

        # Call ContextBuilder to compile prompt context under strict token budgets
        compiled_prompt_str = ContextBuilder.compile_prompt(
            system_instruction=agent.system_prompt,
            retrieved_results=retrieved_results,
            conversation_history=history_payload,
            current_message=user_message,
            max_total_tokens=8000
        )

        sys_hash = PromptEngine.compute_hash(compiled_prompt_str)
        
        prompt_exec = AIPromptExecution(
            conversation_id=conversation.id,
            compiled_prompt=compiled_prompt_str,
            prompt_version=agent.version,
            variables_json=PromptEngine.extract_variables(agent.system_prompt),
            prompt_hash=sys_hash
        )
        db.add(prompt_exec)
        await self._publish_event(ctx, "ai.prompt.compiled", conversation.id, {
            "prompt_hash": sys_hash,
            "prompt_type": "SYSTEM"
        }, request_id)

        # ── OBSERVABILITY: Record prompt span ─────────────────────────────────
        if exec_trace:
            await TraceCollector.record_prompt(
                db=db,
                execution_trace_id=exec_trace.id,
                step_index=1,
                system_prompt=agent.system_prompt,
                compiled_prompt=compiled_prompt_str,
                prompt_hash=sys_hash
            )

        # ── OBSERVABILITY: Record retrieval span ──────────────────────────────
        if exec_trace:
            await TraceCollector.record_retrieval(
                db=db,
                execution_trace_id=exec_trace.id,
                step_index=2,
                query=user_message,
                retrieved_memories_json=[
                    {"source": r.source.value, "content": r.content[:80]}
                    for r in retrieved_results if hasattr(r, "source")
                ],
                vector_hit_count=len(retrieved_results)
            )

        # 4. Fetch Message index & append User Message to DB
        query_msg_count = await db.execute(
            select(func.count(AIMessage.id)).where(AIMessage.conversation_id == conversation.id)
        )
        msg_count = query_msg_count.scalar() or 0

        user_msg = AIMessage(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=user_message,
            message_index=msg_count,
            provider=agent.provider,
            model=agent.model
        )
        db.add(user_msg)
        await db.flush()

        # Build message payloads for LLM Provider (use compiled_prompt_str in first message content)
        llm_messages = [{"role": "user", "content": compiled_prompt_str}]

        # 6. Execute Provider Run loop
        tool_executions = []
        metrics = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_latency_ms": 0
        }
        assistant_msg = await self._run_llm_cycle(
            db, ctx, conversation, agent, llm_messages, credentials, tool_executions, request_id, metrics, exec_trace
        )


        # Trigger Memory Extractors to record facts/preferences in background before returning
        try:
            await MemoryService.extract_memories(db, conversation.id)
        except Exception as memory_err:
            print(f"Memory extraction failed: {str(memory_err)}")

        # 7. Update conversation aggregates
        conversation.status = ConversationStatus.COMPLETED
        conversation.runtime_state = AIRuntimeState.COMPLETED
        conversation.ended_at = datetime.now(timezone.utc)
        
        # Aggregate totals
        conversation.input_tokens = metrics["input_tokens"]
        conversation.output_tokens = metrics["output_tokens"]
        conversation.total_tokens = metrics["input_tokens"] + metrics["output_tokens"]
        conversation.total_latency_ms = metrics["total_latency_ms"]
        conversation.tool_calls_count = len(tool_executions)
        
        await db.flush()

        # ── OBSERVABILITY: Complete execution trace + record metrics ──────────
        if exec_trace:
            await TraceCollector.complete_execution(
                db=db,
                trace=exec_trace,
                status=TraceStatus.SUCCESS,
                total_latency_ms=metrics["total_latency_ms"],
                total_tokens=conversation.total_tokens
            )
            await MetricAggregator.record_metrics(
                db=db,
                trace=exec_trace,
                tool_latency_ms=sum(
                    t.duration_ms for t in tool_executions if t.duration_ms
                ) or None
            )

        return conversation, assistant_msg, tool_executions

    @classmethod
    async def _run_llm_cycle(
        self,
        db: AsyncSession,
        ctx: RequestContext,
        conversation: AIConversation,
        agent: AIAgent,
        llm_messages: list[dict],
        credentials: dict,
        tool_executions: list[AIToolExecution],
        request_id: Optional[uuid.UUID],
        metrics: dict,
        exec_trace=None
    ) -> AIMessage:
        """Invokes provider, validates results, triggers functions, updates execution traces."""
        
        # 1. Update State to LLM_CALL
        conversation.runtime_state = AIRuntimeState.LLM_CALL
        await db.flush()

        # Get Provider
        provider = LLMProviderRegistry.get_provider(agent.provider)

        # Fetch OpenAI compatible schemas
        tools = ToolRegistry.get_all_openai_tools() if agent.supports_tools else None

        await self._publish_event(ctx, "ai.provider.called", conversation.id, {
            "provider": agent.provider,
            "model": agent.model
        }, request_id)

        # Call Provider
        start_time = time.time()
        response = await provider.generate(
            messages=llm_messages,
            model=agent.model,
            tools=tools,
            temperature=agent.temperature,
            max_tokens=agent.max_tokens,
            credentials=credentials
        )
        latency_ms = int((time.time() - start_time) * 1000)

        await self._publish_event(ctx, "ai.provider.completed", conversation.id, {
            "provider": agent.provider,
            "model": agent.model,
            "latency_ms": latency_ms
        }, request_id)

        metrics["input_tokens"] += response.get("input_tokens", 0)
        metrics["output_tokens"] += response.get("output_tokens", 0)
        metrics["total_latency_ms"] += latency_ms

        # Log Token Usage statistics
        token_usage = AITokenUsage(
            conversation_id=conversation.id,
            provider=agent.provider,
            model=agent.model,
            input_tokens=response.get("input_tokens", 0),
            output_tokens=response.get("output_tokens", 0),
            cached_tokens=0,
            reasoning_tokens=0,
            estimated_cost=0.00000
        )
        db.add(token_usage)

        # Extract contents
        content = response.get("content") or ""
        tool_calls = response.get("tool_calls")

        # Resolve message index
        query_msg_count = await db.execute(
            select(func.count(AIMessage.id)).where(AIMessage.conversation_id == conversation.id)
        )
        msg_count = query_msg_count.scalar() or 0

        # Handle tool call iterations
        if tool_calls:
            # Enforce infinite loop protection
            if conversation.tool_iterations >= conversation.max_tool_iterations:
                conversation.status = ConversationStatus.FAILED
                conversation.runtime_state = AIRuntimeState.FAILED
                await db.flush()
                await self._publish_event(ctx, "ai.failed", conversation.id, {
                    "error": "Max tool execution iteration threshold exceeded."
                }, request_id)
                raise ValidationException("AI Runtime loop aborted: too many sequential tool execution calls.")

            conversation.tool_iterations += 1
            conversation.runtime_state = AIRuntimeState.TOOL_EXECUTION
            await db.flush()

            # Append assistant message requesting tool calls
            asst_tc_msg = AIMessage(
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT,
                content=json.dumps(tool_calls),
                message_index=msg_count,
                token_count=response.get("output_tokens", 0),
                latency_ms=latency_ms,
                response_time_ms=latency_ms,
                finish_reason="tool_calls",
                raw_response=response.get("raw_response"),
                provider=agent.provider,
                model=agent.model
            )
            db.add(asst_tc_msg)
            token_usage.message_id = asst_tc_msg.id
            await db.flush()

            llm_messages.append({"role": "assistant", "content": asst_tc_msg.content})

            # Process individual tool calls
            for tc in tool_calls:
                tool_name = tc.get("name")
                tool_args = tc.get("arguments")
                if isinstance(tool_args, str):
                    try:
                        tool_args = json.loads(tool_args)
                    except Exception:
                        tool_args = {}

                # Resolve handler metadata
                handler_name = "Unknown"
                try:
                    tool_def = ToolRegistry.get_tool(tool_name)
                    handler_name = tool_def.handler.__class__.__name__
                except Exception:
                    pass

                # Track tool trace start
                tool_start = time.time()
                tool_exec = AIToolExecution(
                    conversation_id=conversation.id,
                    tool_name=tool_name,
                    handler_name=handler_name,
                    tool_version="1.0",
                    request_id=request_id,
                    input_json=tool_args,
                    output_json={},
                    started_at=datetime.now(timezone.utc),
                    status=ToolExecutionStatus.RUNNING
                )
                db.add(tool_exec)
                await db.flush()

                await self._publish_event(ctx, "ai.tool.started", conversation.id, {
                    "tool_name": tool_name,
                    "handler_name": handler_name
                }, request_id)

                try:
                    # Execute service action
                    output = await ToolRegistry.validate_and_execute(tool_name, tool_args, db, ctx)
                    tool_exec.status = ToolExecutionStatus.SUCCESS
                    tool_exec.output_json = output
                except Exception as ex:
                    tool_exec.status = ToolExecutionStatus.FAILED
                    tool_exec.error_message = str(ex)
                    tool_exec.output_json = {"error": str(ex)}

                tool_exec.finished_at = datetime.now(timezone.utc)
                tool_exec.duration_ms = int((time.time() - tool_start) * 1000)
                tool_executions.append(tool_exec)
                await db.flush()

                # ── OBSERVABILITY: Record tool span ─────────────────────────
                if exec_trace:
                    await TraceCollector.record_tool(
                        db=db,
                        execution_trace_id=exec_trace.id,
                        tool_name=tool_name,
                        step_index=5 + len(tool_executions),
                        arguments_json=tool_args,
                        result_json=tool_exec.output_json,
                        duration_ms=tool_exec.duration_ms,
                        status=TraceStatus.SUCCESS if tool_exec.status == ToolExecutionStatus.SUCCESS else TraceStatus.FAILED,
                        error_message=tool_exec.error_message if tool_exec.status == ToolExecutionStatus.FAILED else None
                    )

                await self._publish_event(ctx, "ai.tool.completed", conversation.id, {
                    "tool_name": tool_name,
                    "status": tool_exec.status
                }, request_id)

                # Append tool response message to database
                query_msg_count = await db.execute(
                    select(func.count(AIMessage.id)).where(AIMessage.conversation_id == conversation.id)
                )
                msg_count = query_msg_count.scalar() or 0

                tool_resp_msg = AIMessage(
                    conversation_id=conversation.id,
                    role=MessageRole.TOOL,
                    content=json.dumps(tool_exec.output_json),
                    message_index=msg_count,
                    provider=agent.provider,
                    model=agent.model
                )
                db.add(tool_resp_msg)
                await db.flush()

                llm_messages.append({"role": "tool", "content": tool_resp_msg.content})

            # Recursively run the next LLM cycle containing tool responses
            return await self._run_llm_cycle(
                db, ctx, conversation, agent, llm_messages, credentials, tool_executions, request_id, metrics, exec_trace
            )

        # No tool calls: finalize response
        conversation.runtime_state = AIRuntimeState.FINAL_RESPONSE
        await db.flush()

        asst_final_msg = AIMessage(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=content,
            message_index=msg_count,
            token_count=response.get("output_tokens", 0),
            latency_ms=latency_ms,
            response_time_ms=latency_ms,
            finish_reason="stop",
            raw_response=response.get("raw_response"),
            provider=agent.provider,
            model=agent.model
        )
        db.add(asst_final_msg)
        token_usage.message_id = asst_final_msg.id
        await db.flush()

        await self._publish_event(ctx, "ai.response.generated", conversation.id, {
            "token_count": asst_final_msg.token_count
        }, request_id)
        await self._publish_event(ctx, "ai.message.generated", conversation.id, {
            "message_id": str(asst_final_msg.id)
        }, request_id)

        return asst_final_msg

    @staticmethod
    async def _publish_event(
        ctx: RequestContext,
        event_name: str,
        conversation_id: uuid.UUID,
        payload: dict,
        request_id: Optional[uuid.UUID]
    ) -> None:
        """Publishes local domain events inside transaction."""
        event_payload = {
            "conversation_id": str(conversation_id),
            **payload
        }
        event = DomainEvent(
            event_name=event_name,
            tenant_id=ctx.tenant_id,
            request_id=request_id or ctx.request_id,
            actor_id=ctx.user.id if ctx.user else None,
            payload=event_payload
        )
        publisher = get_event_publisher()
        await publisher.publish(event)
