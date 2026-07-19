"""
app/governance/risk_engine.py

Risk Scoring Engine Orchestrator.

CTO Refinement #4: Risk plugins architecture.
Aggregates weighted contributions from ActionRiskPlugin, PIIRiskPlugin,
BehaviorRiskPlugin, and ContextRiskPlugin to compute a composite RiskScore (0.0-1.0).

ADR-022: Explainable Decisions — total risk score and plugin breakdown details
are returned in every evaluation.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from app.governance.governance_context import GovernanceContext
from app.governance.risk_plugins import (
    ActionRiskPlugin,
    BaseRiskPlugin,
    BehaviorRiskPlugin,
    ContextRiskPlugin,
    PIIRiskPlugin,
    RiskContribution,
)
from app.models.enums import RiskLevel


@dataclass(frozen=True)
class RiskScoreResult:
    """Composite risk score result."""
    total_score: float
    risk_level: RiskLevel
    contributions: Dict[str, RiskContribution]
    breakdown: Dict[str, float]

    def to_explanation_dict(self) -> Dict[str, Any]:
        return {
            "total_score": round(self.total_score, 4),
            "level": self.risk_level.value,
            "plugin_scores": {k: round(v, 4) for k, v in self.breakdown.items()},
        }


def _classify_risk_level(score: float) -> RiskLevel:
    if score >= 0.90:
        return RiskLevel.CRITICAL
    elif score >= 0.70:
        return RiskLevel.HIGH
    elif score >= 0.50:
        return RiskLevel.MEDIUM
    elif score >= 0.30:
        return RiskLevel.LOW
    return RiskLevel.NEGLIGIBLE


class RiskEngine:
    """Orchestrates risk plugins to evaluate composite risk score for a GovernanceContext."""

    def __init__(self, plugins: Optional[List[BaseRiskPlugin]] = None) -> None:
        self.plugins = plugins or [
            ActionRiskPlugin(),
            PIIRiskPlugin(),
            BehaviorRiskPlugin(),
            ContextRiskPlugin(),
        ]

    def calculate_risk(self, ctx: GovernanceContext) -> RiskScoreResult:
        contributions: Dict[str, RiskContribution] = {}
        breakdown: Dict[str, float] = {}

        total_weighted_score = 0.0
        total_weight = 0.0

        for plugin in self.plugins:
            contrib = plugin.evaluate(ctx)
            contributions[plugin.name] = contrib
            breakdown[plugin.name] = contrib.score
            total_weighted_score += contrib.score * contrib.weight
            total_weight += contrib.weight

        final_score = (
            total_weighted_score / total_weight if total_weight > 0 else 0.0
        )
        final_score = min(1.0, max(0.0, final_score))
        level = _classify_risk_level(final_score)

        return RiskScoreResult(
            total_score=final_score,
            risk_level=level,
            contributions=contributions,
            breakdown=breakdown,
        )


_default_risk_engine = RiskEngine()


def get_risk_engine() -> RiskEngine:
    return _default_risk_engine
