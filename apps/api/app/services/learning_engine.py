import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import EvaluationStatus
from app.models.ai_evaluation import AIEvaluation
from app.services.feedback_collector import FeedbackCollector


class LearningEngine:
    """Orchestrates ingestion of trace runs and feeds them into the collector."""

    @classmethod
    async def process_learning_cycle(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID
    ) -> int:
        """Finds completed evaluations and triggers the FeedbackCollector to add rows."""
        stmt = select(AIEvaluation).where(
            AIEvaluation.organization_id == org_id,
            AIEvaluation.status == EvaluationStatus.COMPLETED
        )
        res = await db.execute(stmt)
        evaluations = res.scalars().all()

        count = 0
        for ev in evaluations:
            # Avoid duplicate inserts by checking if dataset row already exists
            from app.models.ai_learning_dataset import AILearningDataset
            check_stmt = select(AILearningDataset.id).where(
                AILearningDataset.evaluation_id == ev.id
            )
            check_res = await db.execute(check_stmt)
            if check_res.scalar():
                continue

            # Load any feedback associated with it
            from app.models.ai_feedback import AIFeedback
            fb_stmt = select(AIFeedback.id).where(AIFeedback.evaluation_id == ev.id).limit(1)
            fb_res = await db.execute(fb_stmt)
            fb_id = fb_res.scalar()

            dataset_row = await FeedbackCollector.collect_and_save(db, ev.id, fb_id)
            if dataset_row:
                count += 1

        return count
