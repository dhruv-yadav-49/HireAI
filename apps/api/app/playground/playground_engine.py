"""
app/playground/playground_engine.py

Developer Playground Engine Facade.

Main facade orchestrating PlaygroundContext, SandboxRuntime, PromptRunner,
ReplayEngine, ComparisonEngine, GovernanceSimulator, and Metrics.
"""
import uuid
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AIProvider, ComparisonType, PolicyPackType, SandboxIsolationLevel
from app.playground.comparison_engine import ComparisonEngine
from app.playground.evaluation_viewer import EvaluationViewer
from app.playground.experiment_runner import ExperimentRunner
from app.playground.governance_simulator import GovernanceSimulator
from app.playground.model_selector import ModelSelector
from app.playground.playground_context import PlaygroundContext, build_playground_context
from app.playground.prompt_runner import PromptRunner, PromptRunResult
from app.playground.replay_engine import ReplayEngine
from app.playground.trace_viewer import TraceViewer
from app.security.security_context import SecurityContext


class PlaygroundEngine:
    """Facade exposing developer playground operations."""

    def __init__(self, ctx: PlaygroundContext) -> None:
        self.ctx = ctx
        self.prompt_runner = PromptRunner(ctx)
        self.replay_engine = ReplayEngine(ctx)
        self.comparison_engine = ComparisonEngine(ctx)
        self.governance_simulator = GovernanceSimulator(ctx)
        self.experiment_runner = ExperimentRunner(ctx)

    async def execute_prompt_run(
        self,
        template: str,
        variables: Optional[Dict[str, Any]] = None,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> PromptRunResult:
        return await self.prompt_runner.run_prompt(
            template=template,
            variables=variables,
            model_name=model_name,
            temperature=temperature,
        )

    async def replay_trace(
        self,
        db: AsyncSession,
        trace_id: uuid.UUID,
        prompt_override: Optional[str] = None,
        model_override: Optional[str] = None,
        temperature_override: Optional[float] = None,
    ) -> Dict[str, Any]:
        return await self.replay_engine.replay_trace(
            db=db,
            trace_id=trace_id,
            prompt_override=prompt_override,
            model_override=model_override,
            temperature_override=temperature_override,
        )

    async def compare(
        self,
        comparison_type: ComparisonType,
        prompt_a: Optional[str] = None,
        prompt_b: Optional[str] = None,
        models: Optional[List[str]] = None,
        action_type: Optional[str] = None,
        action_payload: Optional[Dict[str, Any]] = None,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if comparison_type == ComparisonType.PROMPT:
            if not prompt_a or not prompt_b:
                raise ValueError("Both prompt_a and prompt_b required for PROMPT comparison.")
            return await self.comparison_engine.compare_prompts(prompt_a, prompt_b, variables)

        elif comparison_type == ComparisonType.MODEL:
            p = prompt_a or "Test prompt"
            m_list = models or ["gpt-4o", "claude-3-5-sonnet", "gemini-1.5-pro"]
            return await self.comparison_engine.compare_models(p, m_list, variables)

        elif comparison_type == ComparisonType.GOVERNANCE:
            act = action_type or "email_send"
            payload = action_payload or {"email": "test@example.com"}
            return self.comparison_engine.compare_governance(act, payload)

        raise ValueError(f"Unsupported comparison type: {comparison_type}")

    def simulate_governance(
        self,
        action_type: str,
        action_payload: Optional[Dict[str, Any]] = None,
        policy_pack_type: PolicyPackType = PolicyPackType.DEFAULT,
    ) -> Dict[str, Any]:
        return self.governance_simulator.simulate_action(
            action_type=action_type,
            action_payload=action_payload,
            policy_pack_type=policy_pack_type,
        )
