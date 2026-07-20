"""
app/marketplace/recommendation_provider.py

Marketplace Recommendation Provider Extension Interface.

CTO Refinement #10:
  Reserves future AI recommendation engine extension hooks:
  Top Rated, Trending, Installed Together, Similar Agents, Organization Recommendations
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class IRecommendationProvider(ABC):
    """Interface for future AI agent recommendation engines (CTO #10)."""

    @abstractmethod
    def get_top_rated(self, limit: int = 10) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_trending(self, limit: int = 10) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_installed_together(self, agent_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_similar_agents(self, agent_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_organization_recommendations(self, org_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        pass
