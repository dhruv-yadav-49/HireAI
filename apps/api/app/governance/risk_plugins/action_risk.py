"""
app/governance/risk_plugins/action_risk.py

Action Risk plugin: Scores inherent risk based on action type.
"""
from app.governance.governance_context import GovernanceContext
from app.governance.risk_plugins.base import BaseRiskPlugin, RiskContribution

_ACTION_RISK_MAP = {
    # High-risk destructive or external actions
    "delete_lead": 0.85,
    "delete_organization": 0.95,
    "export_data": 0.90,
    "bulk_email_send": 0.80,
    "external_api": 0.70,
    "email_send": 0.60,
    "whatsapp_send": 0.60,
    "crm_update": 0.40,
    # Low-risk read-only actions
    "read_crm": 0.10,
    "generate_summary": 0.05,
    "calculate_kpi": 0.05,
}


class ActionRiskPlugin(BaseRiskPlugin):
    """Evaluates risk based on the severity of the action type."""

    @property
    def name(self) -> str:
        return "action_risk"

    @property
    def default_weight(self) -> float:
        return 0.35

    def evaluate(self, ctx: GovernanceContext) -> RiskContribution:
        score = _ACTION_RISK_MAP.get(ctx.action_type, 0.50)
        return RiskContribution(
            plugin_name=self.name,
            score=score,
            weight=self.default_weight,
            details={"action_type": ctx.action_type, "mapped_score": score},
        )
