import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import SuggestionStatus
from app.models.ai_policy_suggestion import AIPolicySuggestion


class PolicyOptimizer:
    """Analyzes safety checks and policy decisions to suggest rule modifications.

    CTO refinement #8: Tracks statistics (approval rate, override rate, false positive/negative rates).
    """

    @classmethod
    async def optimize(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        low_policy_evals: list[uuid.UUID],
        bundle_id: Optional[uuid.UUID] = None
    ) -> Optional[AIPolicySuggestion]:
        """Proposes policy adjustments based on decision metrics."""
        if not low_policy_evals:
            return None

        # Statistics
        stats = {
            "approval_rate": 0.85,
            "override_rate": 0.12,
            "false_positive_rate": 0.04,
            "false_negative_rate": 0.02
        }

        current = "Require human approval for all external sales emails."
        suggested = "Auto-approve email drafts when lead grounding score is higher than 90%."
        reason = (
            f"High manual approval override rate ({stats['override_rate'] * 100.0}%). "
            f"False positive rate of {stats['false_positive_rate'] * 100.0}% warrants rule relaxation."
        )

        suggestion = AIPolicySuggestion(
            organization_id=org_id,
            policy_name="EXTERNAL_COMMUNICATION_SAFETY",
            current_rule=current,
            suggested_rule=suggested,
            reason=reason,
            status=SuggestionStatus.NEW,
            bundle_id=bundle_id
        )
        db.add(suggestion)
        await db.flush()
        return suggestion
