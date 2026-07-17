from typing import Any
from app.models.enums import AgentType


class ConflictResolver:
    @classmethod
    def resolve_conflict(
        cls,
        recommendations: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Deterministically resolves recommendation conflicts.
        Input: list of recommendation dicts:
            {
                "agent_type": AgentType,
                "action": str,
                "confidence": float,
                "priority": "LOW" | "MEDIUM" | "HIGH" | "URGENT",
                "policy_result": "ALLOW" | "REQUIRE_APPROVAL" | "DENY",
                "business_rules": dict
            }
        Returns the winning recommendation dictionary.
        """
        if not recommendations:
            return {}

        priority_weights = {
            "LOW": 1,
            "MEDIUM": 2,
            "HIGH": 3,
            "URGENT": 4
        }

        agent_rank = {
            AgentType.HUMAN: 100,
            AgentType.FINANCE: 90,
            AgentType.SUPPORT: 80,
            AgentType.SALES: 70,
            AgentType.MARKETING: 60,
            AgentType.BUSINESS_ANALYST: 50
        }

        def calculate_score(rec: dict[str, Any]) -> float:
            # Policy constraints override everything
            policy_val = rec.get("policy_result", "ALLOW")
            policy_multiplier = 1.0
            if policy_val == "DENY":
                policy_multiplier = 0.0
            elif policy_val == "REQUIRE_APPROVAL":
                policy_multiplier = 0.5

            priority_str = rec.get("priority", "MEDIUM")
            priority_score = priority_weights.get(priority_str.upper(), 2)

            agent_type = rec.get("agent_type", AgentType.SALES)
            rank_score = agent_rank.get(agent_type, 0)

            confidence = rec.get("confidence", 0.5)

            # Combined weight calculation
            return (rank_score * 10.0 + priority_score * 5.0 + confidence) * policy_multiplier

        scored_recs = []
        for r in recommendations:
            score = calculate_score(r)
            scored_recs.append((score, r))

        # Sort descending by score
        scored_recs.sort(key=lambda x: x[0], reverse=True)
        winner = scored_recs[0][1]

        return {
            "winner": winner,
            "scores": {str(r["agent_type"].value if hasattr(r["agent_type"], 'value') else r["agent_type"]): score for score, r in scored_recs}
        }
