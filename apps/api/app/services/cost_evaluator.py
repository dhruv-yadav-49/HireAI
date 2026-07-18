import uuid
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.ai_execution_trace import AIExecutionTrace


class CostEvaluator:
    """Evaluates estimated financial costs based on token consumption aggregates."""

    @classmethod
    async def evaluate(
        cls,
        db: AsyncSession,
        trace: AIExecutionTrace,
        spans: dict
    ) -> dict[str, Any]:
        """Scores cost against limits (e.g. 0.05 limit per call).

        Standardized output details: {inputs, outputs, score, explanation, warnings}
        """
        cost = float(trace.total_cost) if trace.total_cost else 0.00
        tokens = trace.total_tokens or 0

        score = 100.0
        warnings = []

        # Heuristic limits
        if cost > 0.05:
            score = 60.0
            warnings.append("Cost limits warning: expensive trace generated.")
        elif cost > 0.01:
            score = 90.0

        explanation = f"Run cost estimated at ${cost:.5f} (using {tokens} tokens)."

        return {
            "inputs": {
                "total_tokens": tokens
            },
            "outputs": {
                "total_cost": cost
            },
            "score": score,
            "explanation": explanation,
            "warnings": warnings
        }
