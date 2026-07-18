import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_execution_trace import AIExecutionTrace
from app.models.ai_evaluation import AIEvaluation
from app.models.ai_feedback import AIFeedback
from app.models.ai_learning_dataset import AILearningDataset


class FeedbackCollector:
    """Consumes evaluations and user feedback, saving examples to the append-only learning dataset.

    ADR-018: Immutable Learning Dataset, Evidence-Based Learning.
    """

    @classmethod
    async def collect_and_save(
        cls,
        db: AsyncSession,
        evaluation_id: uuid.UUID,
        feedback_id: Optional[uuid.UUID] = None
    ) -> Optional[AILearningDataset]:
        """Compiles trace and evaluation scores into a learning dataset row. Non-blocking."""
        try:
            eval_record = await db.get(AIEvaluation, evaluation_id)
            if not eval_record:
                return None

            trace = await db.get(AIExecutionTrace, eval_record.execution_trace_id)
            if not trace:
                return None

            feedback = None
            if feedback_id:
                feedback = await db.get(AIFeedback, feedback_id)

            # Ingest context properties (inputs/outputs placeholders)
            dataset_row = AILearningDataset(
                organization_id=eval_record.organization_id,
                execution_trace_id=trace.id,
                evaluation_id=eval_record.id,
                feedback_id=feedback_id,
                agent_type=trace.agent_type,
                input_json={
                    "component": trace.component,
                    "tokens": trace.total_tokens,
                    "trace_id": str(trace.trace_id)
                },
                output_json={
                    "status": trace.status.value,
                    "overall_score": eval_record.overall_score,
                    "grade": eval_record.quality_grade.value if eval_record.quality_grade else None
                },
                expected_output=feedback.comment if feedback else None,
                quality_score=eval_record.overall_score,
                dataset_version=1,
                dataset_source="FEEDBACK" if feedback_id else "EXECUTION"
            )
            db.add(dataset_row)
            await db.flush()
            return dataset_row
        except Exception as e:
            print(f"[FeedbackCollector] Collection failed: {e}")
            return None
