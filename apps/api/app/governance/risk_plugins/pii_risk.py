"""
app/governance/risk_plugins/pii_risk.py

PII Risk plugin: Uses 7C PIIDetector to score presence of sensitive data in payload.
"""
from app.governance.governance_context import GovernanceContext
from app.governance.risk_plugins.base import BaseRiskPlugin, RiskContribution
from app.security.pii_detector import get_pii_detector


class PIIRiskPlugin(BaseRiskPlugin):
    """Evaluates risk by scanning action payload for PII using 7C PIIDetector."""

    @property
    def name(self) -> str:
        return "pii_risk"

    @property
    def default_weight(self) -> float:
        return 0.30

    def evaluate(self, ctx: GovernanceContext) -> RiskContribution:
        detector = get_pii_detector()
        matches = detector.scan_dict(ctx.action_payload) if ctx.action_payload else []

        if not matches:
            return RiskContribution(
                plugin_name=self.name,
                score=0.0,
                weight=self.default_weight,
                details={"pii_matches_count": 0},
            )

        # High score if financial / national ID PII is present
        high_severity_types = {"PAN", "AADHAAR", "CREDIT_CARD"}
        has_high_sev = any(m.pii_type.value in high_severity_types for m in matches)
        score = 0.90 if has_high_sev else 0.60

        return RiskContribution(
            plugin_name=self.name,
            score=score,
            weight=self.default_weight,
            details={
                "pii_matches_count": len(matches),
                "types_found": list({m.pii_type.value for m in matches}),
                "has_high_severity": has_high_sev,
            },
        )
