import uuid
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.ai_execution_trace import AIExecutionTrace


class LatencyEvaluator:
    """Evaluates latency of the complete execution and sub-components."""

    @classmethod
    async def evaluate(
        cls,
        db: AsyncSession,
        trace: AIExecutionTrace,
        spans: dict
    ) -> dict[str, Any]:
        """Scores execution speed against predefined latency SLA targets.

        Standardized output details: {inputs, outputs, score, explanation, warnings}
        """
        # Threshold: standard run completes within 3000ms
        latency = trace.total_latency_ms or 0
        score = 100.0
        warnings = []

        if latency > 5000:
            score = 50.0
            warnings.append("Execution exceeded 5s threshold limit.")
        elif latency > 2000:
            score = 80.0
            warnings.append("Latency warning: slower than target 2s SLA.")

        explanation = f"Execution completed in {latency}ms."

        return {
            "inputs": {
                "started_at": trace.started_at.isoformat() if trace.started_at else None
            },
            "outputs": {
                "total_latency_ms": latency
            },
            "score": score,
            "explanation": explanation,
            "warnings": warnings
        }
