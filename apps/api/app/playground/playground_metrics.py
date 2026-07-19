"""
app/playground/playground_metrics.py

Playground Metrics Service.

CTO Refinement #12: Dedicated PlaygroundMetricsService tracking:
  Experiments count, Average Cost, Average Latency, Provider Usage distribution,
  Prompt Versions Tested, Replay Count.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Any


@dataclass
class PlaygroundMetricsSummary:
    total_experiments: int
    total_prompt_runs: int
    total_replays: int
    average_cost: float
    average_latency_ms: float
    provider_usage: Dict[str, int]
    prompt_versions_tested: List[int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_experiments": self.total_experiments,
            "total_prompt_runs": self.total_prompt_runs,
            "total_replays": self.total_replays,
            "average_cost": round(self.average_cost, 6),
            "average_latency_ms": round(self.average_latency_ms, 2),
            "provider_usage": self.provider_usage,
            "prompt_versions_tested": self.prompt_versions_tested,
        }


class PlaygroundMetricsService:
    """Aggregates developer playground metrics across sessions and trials."""

    @staticmethod
    def compute_summary(runs: List[Dict[str, Any]], replays_count: int = 0) -> PlaygroundMetricsSummary:
        total_runs = len(runs)
        if total_runs == 0:
            return PlaygroundMetricsSummary(
                total_experiments=0,
                total_prompt_runs=0,
                total_replays=replays_count,
                average_cost=0.0,
                average_latency_ms=0.0,
                provider_usage={},
                prompt_versions_tested=[],
            )

        total_cost = sum(float(r.get("token_cost", 0.0)) for r in runs)
        total_latency = sum(int(r.get("latency_ms", 0)) for r in runs)

        provider_usage: Dict[str, int] = {}
        versions = set()

        for r in runs:
            p = r.get("model_name", "mock")
            provider_usage[p] = provider_usage.get(p, 0) + 1
            if "prompt_version" in r:
                versions.add(r["prompt_version"])

        return PlaygroundMetricsSummary(
            total_experiments=total_runs,
            total_prompt_runs=total_runs,
            total_replays=replays_count,
            average_cost=total_cost / total_runs,
            average_latency_ms=total_latency / total_runs,
            provider_usage=provider_usage,
            prompt_versions_tested=sorted(list(versions)),
        )
