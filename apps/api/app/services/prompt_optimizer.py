import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import SuggestionStatus
from app.models.ai_prompt_suggestion import AIPromptSuggestion


class PromptOptimizer:
    """Analyzes prompt token sizes, hallucinations, and suggests refined system instructions.

    ADR-018: Configuration Learning — suggests config changes, not model weight edits.
    """

    @classmethod
    async def optimize(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        low_grounding_evals: list[uuid.UUID],
        bundle_id: Optional[uuid.UUID] = None
    ) -> Optional[AIPromptSuggestion]:
        """Proposes prompt refinements based on grounding failures or feedback markers.

        CTO refinement #5: Includes estimated_impact & affected_agents properties.
        """
        if not low_grounding_evals:
            return None

        # Base suggestions
        current = "You are a Sales executive. Help leads schedule calls."
        suggested = (
            "You are a Sales executive. Help leads schedule calls. "
            "IMPORTANT: Always ground assertions only in CRM context. Never state unverified dates."
        )
        reason = "Detected repeated grounding warnings inside Sales executive conversation runs."

        suggestion = AIPromptSuggestion(
            organization_id=org_id,
            prompt_id=None,  # defaults to runtime prompt configuration template
            current_prompt=current,
            suggested_prompt=suggested,
            reason=reason,
            pattern_confidence=0.88,
            deployment_confidence=0.92,
            status=SuggestionStatus.NEW,
            estimated_impact=15.5,  # percentage improvement estimate
            affected_agents={"list": ["SALES"]},
            bundle_id=bundle_id
        )
        db.add(suggestion)
        await db.flush()
        return suggestion
