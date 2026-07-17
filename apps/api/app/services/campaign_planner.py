import uuid
from typing import Any
from app.models.enums import CampaignGoal, CampaignType, CampaignPriority


class CampaignPlanner:
    @classmethod
    def propose_campaign(
        cls,
        org_id: uuid.UUID,
        objective: CampaignGoal,
        priority: CampaignPriority = CampaignPriority.MEDIUM
    ) -> dict[str, Any]:
        """Proposes a deterministic campaign framework based on a marketing objective."""
        
        # Mapping objectives to strategies
        strategy_mappings = {
            CampaignGoal.LEAD_NURTURING: {
                "campaign_type": CampaignType.EMAIL,
                "name": "Educational Onboarding Sequence",
                "strategy": {
                    "steps": [
                        {"day": 1, "channel": "EMAIL", "template": "onboarding_intro"},
                        {"day": 3, "channel": "EMAIL", "template": "product_features"},
                        {"day": 7, "channel": "EMAIL", "template": "case_study"}
                    ]
                }
            },
            CampaignGoal.REENGAGEMENT: {
                "campaign_type": CampaignType.MULTI_CHANNEL,
                "name": "Inactive Deals Recovery",
                "strategy": {
                    "steps": [
                        {"day": 1, "channel": "EMAIL", "template": "we_miss_you"},
                        {"day": 3, "channel": "WHATSAPP", "template": "quick_nudge"},
                        {"day": 7, "channel": "EMAIL", "template": "exclusive_discount"}
                    ]
                }
            },
            CampaignGoal.LEAD_GENERATION: {
                "campaign_type": CampaignType.NEWSLETTER,
                "name": "Weekly Industry Insights",
                "strategy": {
                    "steps": [
                        {"day": 1, "channel": "EMAIL", "template": "weekly_digest"}
                    ]
                }
            }
        }

        # Fallback Strategy
        default_proposal = {
            "campaign_type": CampaignType.EMAIL,
            "name": f"Outreach - {objective.value}",
            "strategy": {
                "steps": [
                    {"day": 1, "channel": "EMAIL", "template": "standard_outreach"}
                ]
            }
        }

        proposal = strategy_mappings.get(objective, default_proposal)

        return {
            "organization_id": org_id,
            "name": proposal["name"],
            "campaign_type": proposal["campaign_type"],
            "campaign_goal": objective,
            "priority": priority,
            "strategy_json": proposal["strategy"]
        }
