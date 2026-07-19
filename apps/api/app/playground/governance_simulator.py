"""
app/playground/governance_simulator.py

Governance Simulator.

CTO Refinement #7: Simulates governance decisions and decision diffs
between Current Policy and Future Policy without DB mutations.

ADR-023: Safe Experimentation.
"""
from typing import Dict, Any, Optional
from app.governance.governance_context import build_governance_context
from app.governance.governance_engine import get_governance_engine, GovernanceDecisionResult
from app.models.enums import PolicyPackType
from app.playground.playground_context import PlaygroundContext


class GovernanceSimulator:
    """Simulates risk scores and policy decisions under different policy packs."""

    def __init__(self, ctx: PlaygroundContext) -> None:
        self.ctx = ctx
        self.engine = get_governance_engine()

    def simulate_action(
        self,
        action_type: str,
        action_payload: Optional[Dict[str, Any]] = None,
        policy_rules_override: Optional[Dict[str, Any]] = None,
        policy_pack_type: PolicyPackType = PolicyPackType.DEFAULT,
    ) -> Dict[str, Any]:
        gov_ctx = build_governance_context(
            security_context=self.ctx.security_context,
            action_type=action_type,
            action_payload=action_payload or {},
        )

        res: GovernanceDecisionResult = self.engine.evaluate(
            gov_ctx, policy_rules=policy_rules_override, policy_pack_type=policy_pack_type
        )

        return {
            "action_type": action_type,
            "decision_status": res.decision_status.value,
            "risk_score": res.risk_score,
            "risk_level": res.risk_level.value,
            "reason": res.reason,
            "explanation_json": res.explanation_json,
            "policy_name": res.policy_name,
        }

    def simulate_policy_diff(
        self,
        action_type: str,
        action_payload: Dict[str, Any],
        current_policy_type: PolicyPackType = PolicyPackType.DEFAULT,
        future_policy_rules: Optional[Dict[str, Any]] = None,
        future_policy_type: PolicyPackType = PolicyPackType.SOC2,
    ) -> Dict[str, Any]:
        """CTO Refinement #7: Compare decision under Current Policy vs Future Policy."""
        current_res = self.simulate_action(action_type, action_payload, policy_pack_type=current_policy_type)
        future_res = self.simulate_action(
            action_type, action_payload, policy_rules_override=future_policy_rules, policy_pack_type=future_policy_type
        )

        changed = current_res["decision_status"] != future_res["decision_status"]

        return {
            "action_type": action_type,
            "decision_changed": changed,
            "current_policy": current_res,
            "future_policy": future_res,
            "diff_summary": (
                f"Decision changed from {current_res['decision_status']} to {future_res['decision_status']}"
                if changed
                else f"Decision remained unchanged ({current_res['decision_status']})"
            ),
        }
