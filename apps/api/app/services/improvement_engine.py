import uuid
from typing import Optional, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_execution_trace import AIExecutionTrace
from app.models.ai_evaluation import AIEvaluation
from app.models.ai_feedback import AIFeedback
from app.models.ai_approval import AIApproval
from app.models.ai_action import AIAction
from app.models.ai_plan import AIPlan
from app.models.enums import AIApprovalStatus, AIActionType, AIActionStatus, PlannerState
from app.services.prompt_optimizer import PromptOptimizer
from app.services.planner_optimizer import PlannerOptimizer
from app.services.retrieval_optimizer import RetrievalOptimizer
from app.services.policy_optimizer import PolicyOptimizer


class ImprovementEngine:
    """Ingests evaluation failures and groups recommendations into suggestion bundles.

    ADR-018: Configuration Learning, Explainable Suggestions, Human-in-the-Loop.
    """

    @classmethod
    async def run_optimization_cycle(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID
    ) -> dict[str, Any]:
        """Identifies evaluation scores below 85% and runs specialized optimizers.

        CTO refinement #10: Groups suggestions into Suggestion Bundles (linked by bundle_id).
        CTO refinement #11: Governance alignment — creates approval records in ai_approvals.
        """
        # Fetch low evaluations
        eval_stmt = select(AIEvaluation.id).where(
            AIEvaluation.organization_id == org_id,
            AIEvaluation.overall_score < 85.0
        )
        eval_res = await db.execute(eval_stmt)
        low_eval_ids = [r[0] for r in eval_res.fetchall()]

        if not low_eval_ids:
            return {"bundle_id": None, "suggestions_count": 0}

        # 1. Initialize a Suggestion Bundle ID
        bundle_id = uuid.uuid4()

        # 2. Reusing approvals framework: prepare dummy plan and action to satisfy FK constraints
        plan = AIPlan(
            organization_id=org_id,
            agent_type="SALES",
            goal="Observability Optimization Plan",
            plan_json={},
            status=PlannerState.CREATED,
            reasoning_snapshot={}
        )
        db.add(plan)
        await db.flush()

        action = AIAction(
            plan_id=plan.id,
            action_type=AIActionType.REQUEST_APPROVAL,
            status=AIActionStatus.PENDING,
            input_json={}
        )
        db.add(action)
        await db.flush()

        # Helper to create approval trace
        async def create_approval(reason_text: str) -> AIApproval:
            appr = AIApproval(
                action_id=action.id,
                requested_to=None,
                approval_type="MANAGER",
                status=AIApprovalStatus.PENDING,
                reason=reason_text
            )
            db.add(appr)
            await db.flush()
            return appr

        suggestions_count = 0
        prompt_suggestion = None
        policy_suggestion = None

        # 3. Prompt Optimizer
        prompt_appr = await create_approval("Review system prompt optimization suggestion.")
        prompt_suggestion = await PromptOptimizer.optimize(db, org_id, low_eval_ids, bundle_id)
        if prompt_suggestion:
            prompt_suggestion.approval_id = prompt_appr.id
            suggestions_count += 1

        # 4. Policy Optimizer
        policy_appr = await create_approval("Review policy threshold adjustment.")
        policy_suggestion = await PolicyOptimizer.optimize(db, org_id, low_eval_ids, bundle_id)
        if policy_suggestion:
            policy_suggestion.approval_id = policy_appr.id
            suggestions_count += 1

        # 5. Planner and Retrieval Optimizer (estimates / structured changes)
        plan_suggest = await PlannerOptimizer.optimize(db, org_id, low_eval_ids, bundle_id)
        retrieval_suggest = await RetrievalOptimizer.optimize(db, org_id, low_eval_ids, bundle_id)

        # 6. Save AIImprovement log
        from app.models.ai_improvement import AIImprovement
        from app.models.enums import ImprovementType, SuggestionStatus

        improvement = AIImprovement(
            organization_id=org_id,
            improvement_type=ImprovementType.PROMPT,
            current_version="1.0",
            proposed_version="1.1",
            reason=f"Batch execution results triggered {suggestions_count} suggestion adjustments.",
            pattern_confidence=0.85,
            deployment_confidence=0.90,
            status=SuggestionStatus.NEW,
            supporting_evaluation_ids={"ids": [str(i) for i in low_eval_ids]},
            supporting_feedback_ids={"ids": []},
            supporting_trace_ids={"ids": []}
        )
        db.add(improvement)
        await db.flush()

        return {
            "bundle_id": str(bundle_id),
            "suggestions_count": suggestions_count,
            "prompt_suggestion": str(prompt_suggestion.id) if prompt_suggestion else None,
            "policy_suggestion": str(policy_suggestion.id) if policy_suggestion else None,
            "planner_suggestions": plan_suggest,
            "retrieval_suggestions": retrieval_suggest
        }
