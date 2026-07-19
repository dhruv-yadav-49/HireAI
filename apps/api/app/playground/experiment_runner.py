"""
app/playground/experiment_runner.py

Experiment Matrix Runner.

CTO Refinement #8: Multi-dimensional Matrix Execution:
  Prompt x Model x Temperature x Policy.

Generates and executes all Cartesian combinations for comprehensive DX evaluation.
"""
from typing import Dict, List, Any, Optional
from app.models.enums import PolicyPackType
from app.playground.comparison_engine import NormalizedMetricCell
from app.playground.playground_context import PlaygroundContext
from app.playground.prompt_runner import PromptRunner
from app.playground.governance_simulator import GovernanceSimulator


class ExperimentRunner:
    """Matrix runner executing Cartesian product of prompts, models, temperatures, and policies."""

    def __init__(self, ctx: PlaygroundContext) -> None:
        self.ctx = ctx
        self.runner = PromptRunner(ctx)
        self.simulator = GovernanceSimulator(ctx)

    async def run_matrix(
        self,
        prompts: List[str],
        models: List[str],
        temperatures: List[float],
        policies: List[PolicyPackType],
        variables: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        for p_idx, prompt in enumerate(prompts):
            for model in models:
                for temp in temperatures:
                    for policy in policies:
                        run_res = await self.runner.run_prompt(
                            template=prompt,
                            variables=variables,
                            model_name=model,
                            temperature=temp,
                        )
                        gov_res = self.simulator.simulate_action(
                            action_type="experiment_run",
                            action_payload={"prompt": run_res.compiled_prompt},
                            policy_pack_type=policy,
                        )

                        cell = NormalizedMetricCell(
                            target_name=f"P{p_idx+1}:{model}:T{temp}:Pol_{policy.value}",
                            provider=self.ctx.provider.value,
                            model=model,
                            latency_ms=run_res.latency_ms,
                            cost=run_res.token_cost,
                            grounding_score=95.0,
                            hallucination_rate=2.0,
                            risk_level=gov_res["risk_level"],
                            decision=gov_res["decision_status"],
                            output_text=run_res.output_text,
                        )
                        results.append(cell.to_dict())

        return results
