"""
hireai.sdk.plugin — Plugin SDK Module.

CTO Refinements #1, #4:
  - Generalized Plugin Categories: LifecycleHook, RuntimeHook, GovernanceHook, MarketplaceHook
"""
from abc import ABC, abstractmethod
from typing import Any, Dict


class BasePlugin(ABC):
    """Base class for all HireAI ecosystem plugins."""
    @abstractmethod
    def get_plugin_id(self) -> str:
        pass


class LifecycleHook(BasePlugin):
    """Plugin hook intercepting agent initialization and teardown (CTO #4)."""
    def on_agent_init(self, agent_name: str) -> None:
        pass

    def on_agent_teardown(self, agent_name: str) -> None:
        pass

    def get_plugin_id(self) -> str:
        return "lifecycle_hook_default"


class RuntimeHook(BasePlugin):
    """Plugin hook intercepting runtime execution steps (CTO #4)."""
    def pre_step_execute(self, step_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return payload

    def post_step_execute(self, step_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
        return result

    def get_plugin_id(self) -> str:
        return "runtime_hook_default"


class GovernanceHook(BasePlugin):
    """Plugin hook executing custom risk and policy evaluations (CTO #4)."""
    def evaluate_action_risk(self, action_name: str, params: Dict[str, Any]) -> float:
        return 0.1  # Low risk score

    def get_plugin_id(self) -> str:
        return "governance_hook_default"


class MarketplaceHook(BasePlugin):
    """Plugin hook intercepting marketplace install/publish events (CTO #4)."""
    def on_package_installed(self, package_name: str, org_id: str) -> None:
        pass

    def get_plugin_id(self) -> str:
        return "marketplace_hook_default"
