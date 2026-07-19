"""
app/governance/governance_engine.py

Governance Engine Orchestrator.

CTO Refinement #2: Decision Versioning (decision_version, risk_model_version, policy_version).
CTO Refinement #3: Explainability JSON structure.
CTO Refinement #9: Event Bus integration for governance domain events.

ADR-022: Governance by Composition — GovernanceEngine wraps SecurityContext and
evaluates AI actions independently of the core AI runtime.
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.governance.governance_context import GovernanceContext
from app.governance.policy_evaluator import PolicyEvaluator
from app.governance.policy_pack_registry import get_policy_pack_registry
from app.governance.risk_engine import RiskScoreResult, get_risk_engine
from app.models.enums import GovernanceDecisionStatus, PolicyPackType, RiskLevel

logger = logging.getLogger(__name__)

DECISION_VERSION = 1
RISK_MODEL_VERSION = "1.0"
POLICY_VERSION = 1


@dataclass
class GovernanceDecisionResult:
    """Final decision bundle produced by GovernanceEngine."""
    decision_status: GovernanceDecisionStatus
    risk_score: float
    risk_level: RiskLevel
    reason: str
    explanation_json: Dict[str, Any]
    decision_version: int = DECISION_VERSION
    risk_model_version: str = RISK_MODEL_VERSION
    policy_version: int = POLICY_VERSION
    policy_name: str = "HireAI.Default"
    cached: bool = False


# In-memory short TTL decision cache (30 seconds)
_DECISION_CACHE: Dict[str, Tuple[GovernanceDecisionResult, float]] = {}
_CACHE_TTL = 30.0


class GovernanceEngine:
    """Core Governance Engine orchestrating RiskEngine, PolicyEvaluator, and caching."""

    def __init__(self) -> None:
        self.risk_engine = get_risk_engine()
        self.policy_registry = get_policy_pack_registry()

    def evaluate(
        self,
        ctx: GovernanceContext,
        policy_rules: Optional[Dict[str, Any]] = None,
        policy_pack_type: PolicyPackType = PolicyPackType.DEFAULT,
    ) -> GovernanceDecisionResult:
        """Evaluate a GovernanceContext against risk plugins and policy rules."""
        cache_key = ctx.cache_key()
        now = time.monotonic()

        # Cache check
        if cache_key in _DECISION_CACHE:
            cached_res, expires_at = _DECISION_CACHE[cache_key]
            if now < expires_at:
                return GovernanceDecisionResult(
                    decision_status=cached_res.decision_status,
                    risk_score=cached_res.risk_score,
                    risk_level=cached_res.risk_level,
                    reason=cached_res.reason,
                    explanation_json=cached_res.explanation_json,
                    policy_name=cached_res.policy_name,
                    cached=True,
                )

        # 1. Resolve Effective Rules
        pack_def = self.policy_registry.get_pack(policy_pack_type)
        effective_rules = pack_def.rules.copy()
        if policy_rules:
            effective_rules.update(policy_rules)

        # Thresholds
        permit_th = float(effective_rules.get("permit_threshold", 0.30))
        escalate_th = float(effective_rules.get("escalate_threshold", 0.70))
        block_th = float(effective_rules.get("block_threshold", 0.85))

        # 2. Risk Calculation
        risk_result: RiskScoreResult = self.risk_engine.calculate_risk(ctx)

        # 3. Policy Rule Evaluation
        policy_eval = PolicyEvaluator.evaluate(ctx, effective_rules)

        # 4. Synthesize Final Decision
        final_status: GovernanceDecisionStatus
        reason: str

        if policy_eval.forced_decision:
            final_status = policy_eval.forced_decision
            reason = policy_eval.reason or f"Policy forced decision: {final_status.value}"
        elif risk_result.total_score >= block_th:
            final_status = GovernanceDecisionStatus.BLOCK
            reason = f"Risk score ({risk_result.total_score:.2f}) exceeds block threshold ({block_th:.2f})."
        elif risk_result.total_score >= permit_th:
            final_status = GovernanceDecisionStatus.ESCALATE
            reason = f"Risk score ({risk_result.total_score:.2f}) requires human approval (threshold: {permit_th:.2f})."
        else:
            final_status = GovernanceDecisionStatus.PERMIT
            reason = f"Risk score ({risk_result.total_score:.2f}) is within acceptable permit threshold ({permit_th:.2f})."

        # CTO Refinement #3: Structured Explainability JSON
        explanation_json = {
            "risk": risk_result.to_explanation_dict(),
            "policy": {
                "pack_name": pack_def.name,
                "matched_rules": policy_eval.matched_rules,
                "violations": policy_eval.violations,
            },
            "thresholds": {
                "permit": permit_th,
                "escalate": escalate_th,
                "block": block_th,
            },
            "decision": final_status.value,
        }

        result = GovernanceDecisionResult(
            decision_status=final_status,
            risk_score=risk_result.total_score,
            risk_level=risk_result.risk_level,
            reason=reason,
            explanation_json=explanation_json,
            policy_name=pack_def.name,
            cached=False,
        )

        # Store in TTL Cache
        _DECISION_CACHE[cache_key] = (result, now + _CACHE_TTL)

        return result

    @staticmethod
    def clear_cache() -> None:
        _DECISION_CACHE.clear()


_governance_engine = GovernanceEngine()


def get_governance_engine() -> GovernanceEngine:
    return _governance_engine
