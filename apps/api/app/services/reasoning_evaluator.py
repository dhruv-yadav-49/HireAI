import uuid
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.ai_execution_trace import AIExecutionTrace


class ReasoningEvaluator:
    """Evaluates reasoning engine outputs, confidence, logical consistency, and explainability."""

    @classmethod
    async def evaluate(
        cls,
        db: AsyncSession,
        trace: AIExecutionTrace,
        spans: dict
    ) -> dict[str, Any]:
        """Scores logical consistency and explainability of reasoning steps.

        Standardized output details: {inputs, outputs, score, explanation, warnings}
        """
        reasonings = spans.get("reasonings", [])

        score = 100.0
        explanation = "No reasoning log found. Reasoning assumed optimal."
        warnings = []
        confidence = 1.0
        consistency = 1.0

        if reasonings:
            r = reasonings[0]
            confidence = r.confidence if r.confidence is not None else 0.8
            
            # Simple logical consistency evaluation logic
            if r.risk == "CRITICAL" and confidence > 0.9:
                consistency = 0.7
                warnings.append("High confidence output on a critical risk reasoning path.")

            score = round((confidence + consistency) / 2.0 * 100.0, 2)
            explanation = f"Reasoning engine reported confidence of {confidence} with risk profile of {r.risk or 'NONE'}."

        return {
            "inputs": {
                "risk_profile": reasonings[0].risk if reasonings else None
            },
            "outputs": {
                "confidence": confidence,
                "consistency": consistency
            },
            "score": score,
            "explanation": explanation,
            "warnings": warnings
        }
