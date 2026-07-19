"""
app/governance/policy_evaluator.py

Policy Evaluator for AI Governance rules.

Evaluates an action against organization governance rules and policy pack settings.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from app.governance.governance_context import GovernanceContext
from app.models.enums import GovernanceDecisionStatus


@dataclass
class PolicyEvaluationResult:
    """Outcome of governance policy rule evaluation."""
    forced_decision: Optional[GovernanceDecisionStatus] = None
    matched_rules: List[str] = field(default_factory=list)
    violations: List[str] = field(default_factory=list)
    reason: Optional[str] = None


class PolicyEvaluator:
    """Evaluates rules defined within a PolicyPack or org GovernancePolicy."""

    @staticmethod
    def evaluate(ctx: GovernanceContext, rules: Dict[str, Any]) -> PolicyEvaluationResult:
        matched: List[str] = []
        violations: List[str] = []
        forced: Optional[GovernanceDecisionStatus] = None
        reason: Optional[str] = None

        governed_actions = rules.get("governed_actions", [])

        # 1. Action Bypass Check: If action is not in governed_actions list, PERMIT immediately
        if governed_actions and ctx.action_type not in governed_actions:
            return PolicyEvaluationResult(
                forced_decision=GovernanceDecisionStatus.PERMIT,
                matched_rules=["Bypass: Action not in governed_actions list"],
                reason="Action type is exempt from AI governance checks.",
            )

        # 2. Hard Block Rules
        if rules.get("block_unmasked_pii") and ctx.risk_inputs.get("has_unmasked_pii"):
            violations.append("Rule: block_unmasked_pii triggered")
            forced = GovernanceDecisionStatus.BLOCK
            reason = "Action payload contains unmasked PII prohibited by org policy."

        # 3. Explicit Role Exemption / Override
        if "OWNER" in ctx.security_context.roles and rules.get("owner_bypass_governance"):
            matched.append("Rule: owner_bypass_governance applied")
            forced = GovernanceDecisionStatus.PERMIT
            reason = "Organization owner bypass applied."

        return PolicyEvaluationResult(
            forced_decision=forced,
            matched_rules=matched,
            violations=violations,
            reason=reason,
        )
