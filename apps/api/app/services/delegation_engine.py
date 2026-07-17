import uuid
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.enums import AgentType
from app.services.agent_registry import AIAgentRegistry


class DelegationEngine:
    @classmethod
    async def delegate_goal(
        cls,
        db: AsyncSession,
        goal: str
    ) -> dict[str, Any]:
        """
        Determines the candidate agents capable of fulfilling the goal and returns scoring metrics.
        """
        goal_lower = goal.lower()
        candidates = []

        # Fetch capabilities for each agent type to build dynamic scoring
        for agent_type in [
            AgentType.SALES,
            AgentType.SUPPORT,
            AgentType.MARKETING,
            AgentType.BUSINESS_ANALYST,
            AgentType.FINANCE,
            AgentType.HUMAN
        ]:
            capability = await AIAgentRegistry.get_agent_capability(db, agent_type)
            score = 0.1  # base score

            # Match against supported goals keywords
            for sg in capability.supported_goals:
                if sg in goal_lower:
                    score += 0.4
            
            # Match against description keywords
            words = goal_lower.split()
            desc_lower = capability.description.lower()
            for w in words:
                if len(w) > 3 and w in desc_lower:
                    score += 0.1

            # Cap score to [0.0, 1.0] range
            final_score = min(score, 1.0)
            
            candidates.append({
                "agent_type": agent_type,
                "capability_score": final_score,
                "confidence": final_score
            })

        # Sort candidates descending by capability score
        candidates.sort(key=lambda x: x["capability_score"], reverse=True)
        selected = candidates[0]["agent_type"]

        return {
            "selected_agent": selected,
            "candidates": candidates
        }
