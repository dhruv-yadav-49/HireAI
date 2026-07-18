import uuid
import traceback
from datetime import datetime, timezone
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TraceStatus, AgentType, TraceSamplingMode, MetricType
from app.models.ai_execution_trace import AIExecutionTrace
from app.models.ai_prompt_trace import AIPromptTrace
from app.models.ai_retrieval_trace import AIRetrievalTrace
from app.models.ai_reasoning_trace import AIReasoningTrace
from app.models.ai_planning_trace import AIPlanningTrace
from app.models.ai_policy_trace import AIPolicyTrace
from app.models.ai_tool_trace import AIToolTrace


class TraceCollector:
    """Central single write-point for all AI observability traces.

    ADR-016 Principles:
    - Components NEVER write trace records directly.
    - Every method wraps its DB write in try/except — trace failures NEVER abort execution.
    - Observability is passive; it never changes AI execution behavior.
    """

    @classmethod
    async def start_execution(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        agent_type: AgentType,
        conversation_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[uuid.UUID] = None,
        causation_id: Optional[uuid.UUID] = None,
        component: Optional[str] = None,
        sampling_mode: TraceSamplingMode = TraceSamplingMode.FULL,
        parent_span_id: Optional[uuid.UUID] = None
    ) -> Optional[AIExecutionTrace]:
        """Creates a top-level execution trace envelope. Returns None on failure (non-blocking)."""
        try:
            trace = AIExecutionTrace(
                organization_id=org_id,
                trace_id=uuid.uuid4(),
                span_id=uuid.uuid4(),
                parent_span_id=parent_span_id,
                conversation_id=conversation_id,
                execution_id=uuid.uuid4(),
                correlation_id=correlation_id,
                causation_id=causation_id,
                agent_type=agent_type,
                component=component,
                status=TraceStatus.STARTED,
                sampling_mode=sampling_mode,
                started_at=datetime.now(timezone.utc)
            )
            db.add(trace)
            await db.flush()
            return trace
        except Exception as exc:
            print(f"[TraceCollector] start_execution failed (non-blocking): {exc}")
            return None

    @classmethod
    async def complete_execution(
        cls,
        db: AsyncSession,
        trace: Optional[AIExecutionTrace],
        status: TraceStatus = TraceStatus.SUCCESS,
        total_latency_ms: Optional[int] = None,
        total_tokens: Optional[int] = None,
        total_cost: Optional[float] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        exc: Optional[Exception] = None
    ) -> None:
        """Marks execution trace as completed. Non-blocking."""
        if trace is None:
            return
        try:
            trace.status = status
            trace.completed_at = datetime.now(timezone.utc)
            trace.total_latency_ms = total_latency_ms
            trace.total_tokens = total_tokens
            trace.total_cost = total_cost
            if error_type:
                trace.error_type = error_type
            if error_message:
                trace.error_message = error_message
            if exc:
                trace.error_type = type(exc).__name__
                trace.error_message = str(exc)
                trace.stack_trace = traceback.format_exc()
            await db.flush()
        except Exception as e:
            print(f"[TraceCollector] complete_execution failed (non-blocking): {e}")

    @classmethod
    async def record_prompt(
        cls,
        db: AsyncSession,
        execution_trace_id: uuid.UUID,
        step_index: int = 1,
        system_prompt: Optional[str] = None,
        compiled_prompt: Optional[str] = None,
        variables_json: Optional[dict] = None,
        prompt_hash: Optional[str] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        cached_tokens: Optional[int] = None,
        reasoning_tokens: Optional[int] = None,
        latency_ms: Optional[int] = None,
        parent_span_id: Optional[uuid.UUID] = None
    ) -> Optional[AIPromptTrace]:
        """Records prompt compile span. Non-blocking."""
        try:
            pt = AIPromptTrace(
                execution_trace_id=execution_trace_id,
                span_id=uuid.uuid4(),
                parent_span_id=parent_span_id,
                component="PromptEngine",
                step_index=step_index,
                system_prompt=system_prompt,
                compiled_prompt=compiled_prompt,
                variables_json=variables_json or {},
                prompt_hash=prompt_hash,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cached_tokens=cached_tokens,
                reasoning_tokens=reasoning_tokens,
                latency_ms=latency_ms
            )
            db.add(pt)
            await db.flush()
            return pt
        except Exception as e:
            print(f"[TraceCollector] record_prompt failed (non-blocking): {e}")
            return None

    @classmethod
    async def record_retrieval(
        cls,
        db: AsyncSession,
        execution_trace_id: uuid.UUID,
        step_index: int = 2,
        query: Optional[str] = None,
        retrieved_memories_json: Optional[list] = None,
        retrieved_knowledge_json: Optional[list] = None,
        retrieved_crm_json: Optional[list] = None,
        vector_hit_count: Optional[int] = None,
        memory_latency_ms: Optional[int] = None,
        crm_latency_ms: Optional[int] = None,
        knowledge_latency_ms: Optional[int] = None,
        vector_search_latency_ms: Optional[int] = None,
        total_retrieval_latency_ms: Optional[int] = None,
        parent_span_id: Optional[uuid.UUID] = None
    ) -> Optional[AIRetrievalTrace]:
        """Records retrieval span with per-source timings. Non-blocking."""
        try:
            rt = AIRetrievalTrace(
                execution_trace_id=execution_trace_id,
                span_id=uuid.uuid4(),
                parent_span_id=parent_span_id,
                component="RetrievalService",
                step_index=step_index,
                query=query,
                retrieved_memories_json=retrieved_memories_json or [],
                retrieved_knowledge_json=retrieved_knowledge_json or [],
                retrieved_crm_json=retrieved_crm_json or [],
                vector_hit_count=vector_hit_count,
                memory_latency_ms=memory_latency_ms,
                crm_latency_ms=crm_latency_ms,
                knowledge_latency_ms=knowledge_latency_ms,
                vector_search_latency_ms=vector_search_latency_ms,
                total_retrieval_latency_ms=total_retrieval_latency_ms
            )
            db.add(rt)
            await db.flush()
            return rt
        except Exception as e:
            print(f"[TraceCollector] record_retrieval failed (non-blocking): {e}")
            return None

    @classmethod
    async def record_reasoning(
        cls,
        db: AsyncSession,
        execution_trace_id: uuid.UUID,
        step_index: int = 3,
        reason: Optional[str] = None,
        confidence: Optional[float] = None,
        priority: Optional[str] = None,
        risk: Optional[str] = None,
        expected_outcome: Optional[str] = None,
        parent_span_id: Optional[uuid.UUID] = None
    ) -> Optional[AIReasoningTrace]:
        """Records reasoning engine output span. Non-blocking."""
        try:
            rr = AIReasoningTrace(
                execution_trace_id=execution_trace_id,
                span_id=uuid.uuid4(),
                parent_span_id=parent_span_id,
                component="ReasoningEngine",
                step_index=step_index,
                reason=reason,
                confidence=confidence,
                priority=priority,
                risk=risk,
                expected_outcome=expected_outcome
            )
            db.add(rr)
            await db.flush()
            return rr
        except Exception as e:
            print(f"[TraceCollector] record_reasoning failed (non-blocking): {e}")
            return None

    @classmethod
    async def record_planning(
        cls,
        db: AsyncSession,
        execution_trace_id: uuid.UUID,
        step_index: int = 4,
        goal: Optional[str] = None,
        plan_json: Optional[dict] = None,
        planner_version: Optional[str] = None,
        planning_tokens: Optional[int] = None,
        latency_ms: Optional[int] = None,
        parent_span_id: Optional[uuid.UUID] = None
    ) -> Optional[AIPlanningTrace]:
        """Records planner output span. Non-blocking."""
        try:
            pp = AIPlanningTrace(
                execution_trace_id=execution_trace_id,
                span_id=uuid.uuid4(),
                parent_span_id=parent_span_id,
                component="Planner",
                step_index=step_index,
                goal=goal,
                plan_json=plan_json or {},
                planner_version=planner_version or "1.0",
                planning_tokens=planning_tokens,
                latency_ms=latency_ms
            )
            db.add(pp)
            await db.flush()
            return pp
        except Exception as e:
            print(f"[TraceCollector] record_planning failed (non-blocking): {e}")
            return None

    @classmethod
    async def record_policy(
        cls,
        db: AsyncSession,
        execution_trace_id: uuid.UUID,
        step_index: int = 5,
        policy: Optional[str] = None,
        decision: Optional[str] = None,
        risk: Optional[str] = None,
        reason: Optional[str] = None,
        latency_ms: Optional[int] = None,
        parent_span_id: Optional[uuid.UUID] = None
    ) -> Optional[AIPolicyTrace]:
        """Records policy engine decision span. Non-blocking."""
        try:
            pol = AIPolicyTrace(
                execution_trace_id=execution_trace_id,
                span_id=uuid.uuid4(),
                parent_span_id=parent_span_id,
                component="PolicyEngine",
                step_index=step_index,
                policy=policy,
                decision=decision,
                risk=risk,
                reason=reason,
                latency_ms=latency_ms
            )
            db.add(pol)
            await db.flush()
            return pol
        except Exception as e:
            print(f"[TraceCollector] record_policy failed (non-blocking): {e}")
            return None

    @classmethod
    async def record_tool(
        cls,
        db: AsyncSession,
        execution_trace_id: uuid.UUID,
        tool_name: str,
        step_index: int = 6,
        arguments_json: Optional[dict] = None,
        result_json: Optional[dict] = None,
        duration_ms: Optional[int] = None,
        retries: int = 0,
        status: TraceStatus = TraceStatus.SUCCESS,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        stack_trace: Optional[str] = None,
        parent_span_id: Optional[uuid.UUID] = None
    ) -> Optional[AIToolTrace]:
        """Records a tool call span. Non-blocking."""
        try:
            tt = AIToolTrace(
                execution_trace_id=execution_trace_id,
                span_id=uuid.uuid4(),
                parent_span_id=parent_span_id,
                component=tool_name,
                step_index=step_index,
                tool_name=tool_name,
                arguments_json=arguments_json or {},
                result_json=result_json or {},
                duration_ms=duration_ms,
                retries=retries,
                status=status,
                error_type=error_type,
                error_message=error_message,
                stack_trace=stack_trace
            )
            db.add(tt)
            await db.flush()
            return tt
        except Exception as e:
            print(f"[TraceCollector] record_tool failed (non-blocking): {e}")
            return None
