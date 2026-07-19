"""
app/governance/risk_plugins/context_risk.py

Context Risk plugin: Evaluates environmental factors (off-hours, anomaly).
"""
from datetime import datetime, timezone
from app.governance.governance_context import GovernanceContext
from app.governance.risk_plugins.base import BaseRiskPlugin, RiskContribution


class ContextRiskPlugin(BaseRiskPlugin):
    """Evaluates contextual risk factors (e.g. execution timing, rapid volume spikes)."""

    @property
    def name(self) -> str:
        return "context_risk"

    @property
    def default_weight(self) -> float:
        return 0.15

    def evaluate(self, ctx: GovernanceContext) -> RiskContribution:
        now = datetime.now(timezone.utc)
        # Off-hours execution check (e.g. 10 PM - 5 AM UTC)
        is_off_hours = now.hour >= 22 or now.hour <= 5
        score = 0.40 if is_off_hours else 0.10

        if ctx.risk_inputs.get("volume_anomaly"):
            score += 0.30

        score = min(1.0, score)

        return RiskContribution(
            plugin_name=self.name,
            score=score,
            weight=self.default_weight,
            details={"is_off_hours": is_off_hours, "final_score": score},
        )
