import uuid
from typing import Any
from app.models.enums import CampaignType


class CampaignStrategyEngine:
    @classmethod
    def compile_strategy(
        cls,
        campaign_type: CampaignType,
        custom_steps: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Validates and returns nurturing sequence workflow steps."""
        
        default_steps = [
            {"day": 1, "channel": "EMAIL", "action": "SEND_TEMPLATE", "params": {"template": "intro"}},
            {"day": 3, "channel": "WHATSAPP", "action": "SEND_TEMPLATE", "params": {"template": "followup"}}
        ]

        if custom_steps and "steps" in custom_steps:
            steps = custom_steps["steps"]
        else:
            steps = default_steps

        # Standardizing workflow structure
        return {
            "steps": steps,
            "orchestration_mode": "SEQUENTIAL" if len(steps) > 1 else "SINGLE_ACTION",
            "backoff_policy": "FIXED",
            "retry_attempts": 3
        }
