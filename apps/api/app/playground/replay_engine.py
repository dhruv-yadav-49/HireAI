"""
app/playground/replay_engine.py

Historical Execution Replay Engine.

CTO Refinement #5: Supports replaying historical execution traces (Sprint 6A)
with optional overrides for Prompt, Model, Policy, or Temperature without
modifying production history.

ADR-023: Safe Replay.
"""
import uuid
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.ai_execution_trace import AIExecutionTrace
from app.playground.playground_context import PlaygroundContext
from app.playground.prompt_runner import PromptRunner, PromptRunResult


class ReplayEngine:
    """Loads historical execution traces and re-runs dispatches in Sandbox mode."""

    def __init__(self, ctx: PlaygroundContext) -> None:
        self.ctx = ctx
        self.runner = PromptRunner(ctx)

    async def replay_trace(
        self,
        db: AsyncSession,
        trace_id: uuid.UUID,
        prompt_override: Optional[str] = None,
        model_override: Optional[str] = None,
        temperature_override: Optional[float] = None,
        variables_override: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        # 1. Fetch historical trace
        stmt = select(AIExecutionTrace).where(AIExecutionTrace.id == trace_id)
        res = await db.execute(stmt)
        trace = res.scalar_one_or_none()

        if not trace:
            raise ValueError(f"Execution trace {trace_id} not found.")

        # 2. Extract original configuration
        original_prompt = trace.action_payload.get("prompt", "Analyze request") if trace.action_payload else "Analyze request"
        original_model = trace.action_payload.get("model", "mock-llm-v1") if trace.action_payload else "mock-llm-v1"

        target_prompt = prompt_override or original_prompt
        target_model = model_override or original_model
        target_temp = temperature_override if temperature_override is not None else self.ctx.temperature

        # 3. Re-run via Sandbox PromptRunner
        run_res: PromptRunResult = await self.runner.run_prompt(
            template=target_prompt,
            variables=variables_override or {},
            model_name=target_model,
            temperature=target_temp,
        )

        return {
            "trace_id": str(trace_id),
            "original": {
                "prompt": original_prompt,
                "model": original_model,
                "status": trace.status.value if trace.status else "COMPLETED",
            },
            "replayed": {
                "prompt": run_res.prompt_text,
                "compiled_prompt": run_res.compiled_prompt,
                "output_text": run_res.output_text,
                "model_name": run_res.model_name,
                "latency_ms": run_res.latency_ms,
                "token_cost": run_res.token_cost,
                "prompt_hash": run_res.prompt_hash,
                "compiled_prompt_hash": run_res.compiled_prompt_hash,
            },
            "overrides_applied": {
                "prompt_overridden": prompt_override is not None,
                "model_overridden": model_override is not None,
                "temperature_overridden": temperature_override is not None,
            },
        }
