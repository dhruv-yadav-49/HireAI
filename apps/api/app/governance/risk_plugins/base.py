"""
app/governance/risk_plugins/base.py

Abstract Base class for Risk Plugins.

CTO Refinement #4: Risk plugins architecture.
Individual risk dimensions (Action, PII, Behavior, Context) implement BaseRiskPlugin.
The RiskEngine aggregates plugin scores via weighted combination.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any
from app.governance.governance_context import GovernanceContext


@dataclass(frozen=True)
class RiskContribution:
    """Risk contribution from a single plugin."""
    plugin_name: str
    score: float       # 0.0 to 1.0
    weight: float      # Weight in global score
    details: Dict[str, Any]


class BaseRiskPlugin(ABC):
    """Interface for risk scoring plugins."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def default_weight(self) -> float:
        ...

    @abstractmethod
    def evaluate(self, ctx: GovernanceContext) -> RiskContribution:
        """Evaluate risk contribution for a governance context."""
        ...
