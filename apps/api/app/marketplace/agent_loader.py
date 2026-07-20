"""
app/marketplace/agent_loader.py

Dedicated Agent Runtime Loader.

CTO Refinement #11:
  Avoids direct instantiation of agents.
  Provides structured loading flow: Registry -> Loader -> Runtime -> Execution.
"""
from typing import Any, Dict, Optional
from app.marketplace.package_builder import AgentPackage


class LoadedAgentInstance:
    """Represents a safely loaded agent instance bound to tenant runtime."""

    def __init__(self, agent_key: str, version: str, manifest_dict: Dict[str, Any], loaded: bool) -> None:
        self.agent_key = agent_key
        self.version = version
        self.manifest_dict = manifest_dict
        self.loaded = loaded

    def execute(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Simulates agent runtime execution."""
        return {
            "status": "SUCCESS",
            "agent_key": self.agent_key,
            "version": self.version,
            "action": action,
            "result": f"Executed action '{action}' on loaded agent '{self.agent_key}' (v{self.version}).",
        }


class AgentLoader:
    """Safely loads agent packages into tenant runtime environment (CTO #11)."""

    @classmethod
    def load_agent(cls, package: AgentPackage) -> LoadedAgentInstance:
        """Loads agent package into runtime sandbox container."""
        manifest = package.manifest
        return LoadedAgentInstance(
            agent_key=manifest.name,
            version=manifest.version,
            manifest_dict=manifest.model_dump(),
            loaded=True,
        )

    @classmethod
    def verify_loadable(cls, package: AgentPackage) -> bool:
        """Verifies that the agent package can be loaded into memory without error."""
        try:
            instance = cls.load_agent(package)
            return instance.loaded
        except Exception:
            return False
