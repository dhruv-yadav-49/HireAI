"""
hireai.sdk.agent — Agent SDK Module.

CTO Refinements #1, #2:
  - BaseAgent abstract class
  - Formalized around AgentContext (security, governance, memory, runtime, trace, logger)
  - @agent decorator binding manifest metadata
  - AgentPackager for building .hireagent artifacts
"""
import uuid
import yaml
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentContext(BaseModel):
    """Context object passed to agent execution (CTO #2)."""

    tenant_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    security_context: Dict[str, Any] = Field(default_factory=dict)
    governance_context: Dict[str, Any] = Field(default_factory=dict)
    memory_store: Dict[str, Any] = Field(default_factory=dict)
    trace_id: str = Field(default_factory=lambda: f"trc_{uuid.uuid4().hex[:12]}")
    cancellation_requested: bool = False
    logger_prefix: str = "[AgentSDK]"


class BaseAgent(ABC):
    """Abstract base class for authoring custom HireAI AI Employees (CTO #2)."""

    def __init__(self, name: str, version: str = "1.0.0") -> None:
        self.name = name
        self.version = version
        self.registered_tools: List[str] = []

    @abstractmethod
    def execute(self, ctx: AgentContext, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Core execution logic receiving AgentContext (CTO #2)."""
        pass

    def register_tool(self, tool_name: str) -> None:
        if tool_name not in self.registered_tools:
            self.registered_tools.append(tool_name)


def agent(
    name: str,
    version: str = "1.0.0",
    display_name: Optional[str] = None,
    description: Optional[str] = None,
    permissions: Optional[List[str]] = None,
    required_tools: Optional[List[str]] = None,
    required_models: Optional[List[str]] = None,
    depends_on: Optional[List[str]] = None,
) -> Callable:
    """Decorator binding manifest metadata to custom BaseAgent classes (CTO #2)."""

    def decorator(cls: type) -> type:
        cls.__hireai_agent_meta__ = {
            "name": name,
            "version": version,
            "display_name": display_name or name.replace("-", " ").title(),
            "description": description or f"Custom AI Agent {name}",
            "permissions": permissions or [],
            "required_tools": required_tools or [],
            "required_models": required_models or ["gpt-4o"],
            "depends_on": depends_on or [],
        }
        return cls

    return decorator


class AgentPackager:
    """Programmatically packs custom agent into .hireagent deployable artifact (CTO #2)."""

    @classmethod
    def create_manifest_yaml(cls, meta: Dict[str, Any]) -> str:
        """Generates standard manifest.yaml string from meta dictionary."""
        manifest_dict = {
            "name": meta.get("name", "custom-agent"),
            "display_name": meta.get("display_name", "Custom Agent"),
            "description": meta.get("description", "Custom AI Agent"),
            "version": meta.get("version", "1.0.0"),
            "manifest_version": 1,
            "api_version": "1.0",
            "sdk_version": ">=1.0",
            "runtime": ">=1.0",
            "entrypoint": "agent.py",
            "permissions": meta.get("permissions", []),
            "required_tools": meta.get("required_tools", []),
            "required_models": meta.get("required_models", ["gpt-4o"]),
            "depends_on": meta.get("depends_on", []),
            "supported_languages": ["en"],
            "governance_policy": "DEFAULT",
            "security_profile": "STANDARD",
        }
        return yaml.dump(manifest_dict, sort_keys=False)
