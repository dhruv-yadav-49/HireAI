import uuid
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.ai_execution_trace import AIExecutionTrace


class PolicyEvaluator:
    """Evaluates safety/policy compliance checks and violation rules."""

    @classmethod
    async def evaluate(
        cls,
        db: AsyncSession,
        trace: AIExecutionTrace,
        spans: dict
    ) -> dict[str, Any]:
        """Scores policy decisions and compliance violations.

        Standardized output details: {inputs, outputs, score, explanation, warnings}
        """
        policies = spans.get("policies", [])

        score = 100.0
        explanation = "No policy checks required. Policy compliance optimal."
        warnings = []
        violations = 0

        if policies:
            blocked_policies = [p for p in policies if p.decision in ("DENY", "BLOCK")]
            pending_approvals = [p for p in policies if p.decision == "REQUIRE_APPROVAL"]

            if blocked_policies:
                violations += len(blocked_policies)
                score = 0.0  # Force zero on block compliance violation
                explanation = f"Critical safety violation: {blocked_policies[0].policy} policy DENIED."
                warnings.append("Security block triggered.")
            elif pending_approvals:
                score = 80.0
                explanation = f"Policy required approval for {pending_approvals[0].policy}."
                warnings.append("Requires human approval context.")
            else:
                score = 100.0
                explanation = "All policy decisions successfully ALLOWED."

        return {
            "inputs": {
                "policies_checked": [p.policy for p in policies]
            },
            "outputs": {
                "violations_count": violations,
                "decisions": [p.decision for p in policies]
            },
            "score": score,
            "explanation": explanation,
            "warnings": warnings
        }
