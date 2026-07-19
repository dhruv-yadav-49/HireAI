"""
app/governance/risk_plugins/behavior_risk.py

Behavior / Historical Risk plugin.
"""
from app.governance.governance_context import GovernanceContext
from app.governance.risk_plugins.base import BaseRiskPlugin, RiskContribution


class BehaviorRiskPlugin(BaseRiskPlugin):
    """Evaluates risk based on historical agent performance and historical rejection rates."""

    @property
    def name(self) -> str:
        return "behavior_risk"

    @property
    def default_weight(self) -> float:
        return 0.20

    def evaluate(self, ctx: GovernanceContext) -> RiskContribution:
        # Check if risk inputs explicitly supply historical rejection metrics
        rejection_rate = ctx.risk_inputs.get("historical_rejection_rate", 0.10)
        score = min(1.0, max(0.0, float(rejection_rate)))

        return RiskContribution(
            plugin_name=self.name,
            score=score,
            weight=self.default_weight,
            details={"historical_rejection_rate": score},
        )
