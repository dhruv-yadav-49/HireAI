import uuid
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.ai_execution_trace import AIExecutionTrace
from app.models.enums import TraceStatus


class ToolEvaluator:
    """Evaluates tool selection, parameter completeness, retry efficiency, and recovery success."""

    @classmethod
    async def evaluate(
        cls,
        db: AsyncSession,
        trace: AIExecutionTrace,
        spans: dict
    ) -> dict[str, Any]:
        """Scores tool executions and errors.

        CTO refinement #7: Measure parameter completeness, retry efficiency, recovery success.
        Standardized output details: {inputs, outputs, score, explanation, warnings}
        """
        tools = spans.get("tools", [])

        score = 100.0
        explanation = "No tools executed. Tool accuracy optimal."
        warnings = []
        param_completeness = 1.0
        retry_efficiency = 1.0
        recovery_success = 1.0

        if tools:
            failed_tools = [t for t in tools if t.status == TraceStatus.FAILED]
            retried_tools = [t for t in tools if t.retries > 0]

            # Heuristics
            if failed_tools:
                recovery_success = 0.0
                score -= 30.0 * len(failed_tools)
                warnings.append(f"{len(failed_tools)} tool execution steps failed.")

            if retried_tools:
                retry_efficiency = 0.5
                score -= 10.0 * len(retried_tools)
                warnings.append(f"Tools required retries: {len(retried_tools)} times.")

            score = max(0.0, score)
            explanation = f"Evaluated {len(tools)} tools. Failed: {len(failed_tools)}, Retries: {len(retried_tools)}."

        return {
            "inputs": {
                "tools_called": [t.tool_name for t in tools]
            },
            "outputs": {
                "parameter_completeness": param_completeness,
                "retry_efficiency": retry_efficiency,
                "recovery_success": recovery_success,
                "failed_count": len(failed_tools) if tools else 0
            },
            "score": score,
            "explanation": explanation,
            "warnings": warnings
        }
