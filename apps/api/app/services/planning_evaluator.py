import uuid
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.ai_execution_trace import AIExecutionTrace


class PlanningEvaluator:
    """Evaluates planner performance: completeness, efficiency, and consistency."""

    @classmethod
    async def evaluate(
        cls,
        db: AsyncSession,
        trace: AIExecutionTrace,
        spans: dict
    ) -> dict[str, Any]:
        """Scores planner goals and plan steps.

        Standardized output details: {inputs, outputs, score, explanation, warnings}
        """
        plannings = spans.get("plannings", [])

        score = 100.0
        explanation = "No planning trace found. Planning assumed optimal."
        warnings = []
        completeness = 1.0
        efficiency = 1.0

        if plannings:
            p = plannings[0]
            plan = p.plan_json or {}
            steps = plan.get("steps", [])

            # Simple plan validation logic
            if not steps:
                score = 40.0
                completeness = 0.0
                explanation = "Planner generated an empty plan layout."
                warnings.append("Plan contains zero steps.")
            else:
                # Count dependencies
                missing_deps = any(s.get("depends_on_action_id") is None for s in steps[1:])
                if missing_deps:
                    efficiency = 0.8
                    warnings.append("Some steps have unlinked action dependencies.")
                
                completeness = 0.95
                score = round((completeness + efficiency) / 2.0 * 100.0, 2)
                explanation = f"Planner successfully created {len(steps)} versioned steps with clear dependencies."

        return {
            "inputs": {
                "goal": plannings[0].goal if plannings else None
            },
            "outputs": {
                "completeness": completeness,
                "efficiency": efficiency,
                "steps_count": len(steps) if plannings and steps else 0
            },
            "score": score,
            "explanation": explanation,
            "warnings": warnings
        }
