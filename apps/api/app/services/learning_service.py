import uuid
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.context import RequestContext
from app.core.events import DomainEvent, get_event_publisher
from app.models.enums import SuggestionStatus, LearningStatus, LearningTriggerMode
from app.models.ai_learning_dataset import AILearningDataset
from app.models.ai_improvement import AIImprovement
from app.models.ai_prompt_suggestion import AIPromptSuggestion
from app.models.ai_policy_suggestion import AIPolicySuggestion
from app.repositories.learning_repository import LearningRepository
from app.services.learning_scheduler import LearningScheduler


class LearningService:
    """Service layer managing feedback datasets, scheduler invocations, and review workflows."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = LearningRepository(db)

    async def _publish(self, ctx: RequestContext, event_name: str, payload: dict) -> None:
        event = DomainEvent(
            event_name=event_name,
            tenant_id=ctx.tenant_id,
            request_id=ctx.request_id,
            actor_id=ctx.user.id if ctx.user else None,
            payload=payload
        )
        try:
            pub = get_event_publisher()
            await pub.publish(event)
        except Exception:
            pass

    async def run_manual_learning(
        self,
        ctx: RequestContext
    ) -> dict:
        """Triggers the learning loop immediately."""
        res = await LearningScheduler.run_scheduler(
            db=self.db,
            org_id=ctx.tenant_id,
            trigger_mode=LearningTriggerMode.MANUAL
        )
        return res

    async def list_datasets(
        self,
        ctx: RequestContext,
        page: int = 1,
        page_size: int = 20
    ) -> dict:
        items, total = await self.repo.list_datasets(ctx, page, page_size)
        return {
            "items": [
                {
                    "id": str(d.id),
                    "execution_trace_id": str(d.execution_trace_id) if d.execution_trace_id else None,
                    "evaluation_id": str(d.evaluation_id) if d.evaluation_id else None,
                    "feedback_id": str(d.feedback_id) if d.feedback_id else None,
                    "agent_type": d.agent_type.value,
                    "input_json": d.input_json,
                    "output_json": d.output_json,
                    "expected_output": d.expected_output,
                    "quality_score": d.quality_score,
                    "dataset_version": d.dataset_version,
                    "dataset_source": d.dataset_source,
                    "created_at": d.created_at.isoformat() if d.created_at else None
                }
                for d in items
            ],
            "total": total,
            "page": page,
            "page_size": page_size
        }

    async def list_improvements(
        self,
        ctx: RequestContext,
        status: Optional[SuggestionStatus] = None,
        page: int = 1,
        page_size: int = 20
    ) -> dict:
        items, total = await self.repo.list_improvements(ctx, status, page, page_size)
        return {
            "items": [
                {
                    "id": str(i.id),
                    "improvement_type": i.improvement_type.value,
                    "current_version": i.current_version,
                    "proposed_version": i.proposed_version,
                    "reason": i.reason,
                    "pattern_confidence": i.pattern_confidence,
                    "deployment_confidence": i.deployment_confidence,
                    "status": i.status.value,
                    "supporting_evaluation_ids": i.supporting_evaluation_ids,
                    "supporting_feedback_ids": i.supporting_feedback_ids,
                    "supporting_trace_ids": i.supporting_trace_ids,
                    "created_at": i.created_at.isoformat() if i.created_at else None
                }
                for i in items
            ],
            "total": total,
            "page": page,
            "page_size": page_size
        }

    async def approve_suggestion(
        self,
        ctx: RequestContext,
        suggestion_id: uuid.UUID,
        suggestion_type: str
    ) -> dict:
        """Approve a prompt or policy suggestion (CTO refinement #11)."""
        target: Optional[Any] = None
        if suggestion_type == "prompt":
            target = await self.repo.get_prompt_suggestion(ctx, suggestion_id)
        elif suggestion_type == "policy":
            target = await self.repo.get_policy_suggestion(ctx, suggestion_id)

        if not target:
            raise ValueError("Suggestion not found or unauthorized.")

        target.status = SuggestionStatus.APPROVED
        await self.db.flush()

        await self._publish(ctx, "learning.suggestion.approved", {
            "suggestion_id": str(suggestion_id),
            "suggestion_type": suggestion_type
        })

        return {"suggestion_id": str(suggestion_id), "status": target.status.value}

    async def reject_suggestion(
        self,
        ctx: RequestContext,
        suggestion_id: uuid.UUID,
        suggestion_type: str
    ) -> dict:
        target: Optional[Any] = None
        if suggestion_type == "prompt":
            target = await self.repo.get_prompt_suggestion(ctx, suggestion_id)
        elif suggestion_type == "policy":
            target = await self.repo.get_policy_suggestion(ctx, suggestion_id)

        if not target:
            raise ValueError("Suggestion not found or unauthorized.")

        target.status = SuggestionStatus.REJECTED
        await self.db.flush()

        await self._publish(ctx, "learning.suggestion.rejected", {
            "suggestion_id": str(suggestion_id),
            "suggestion_type": suggestion_type
        })

        return {"suggestion_id": str(suggestion_id), "status": target.status.value}

    async def get_learning_analytics(
        self,
        ctx: RequestContext
    ) -> dict:
        """Compiles health metrics for continuous learning dashboards.

        CTO refinement #12: average confidence, acceptance rate.
        """
        # Suggestion aggregates
        stmt = select(AIImprovement).where(AIImprovement.organization_id == ctx.tenant_id)
        res = await self.db.execute(stmt)
        improvements = res.scalars().all()

        total = len(improvements)
        if total == 0:
            return {
                "suggestions_generated": 0,
                "approved_count": 0,
                "rejected_count": 0,
                "acceptance_rate": 0.0,
                "avg_pattern_confidence": 0.0,
                "avg_deployment_confidence": 0.0
            }

        approved = sum(1 for i in improvements if i.status == SuggestionStatus.APPROVED)
        rejected = sum(1 for i in improvements if i.status == SuggestionStatus.REJECTED)
        
        avg_pattern_conf = sum(i.pattern_confidence for i in improvements) / total
        avg_dep_conf = sum(i.deployment_confidence for i in improvements) / total

        acceptance_rate = approved / total if total > 0 else 0.0

        return {
            "suggestions_generated": total,
            "approved_count": approved,
            "rejected_count": rejected,
            "acceptance_rate": round(acceptance_rate, 4),
            "avg_pattern_confidence": round(avg_pattern_conf, 4),
            "avg_deployment_confidence": round(avg_dep_conf, 4)
        }
