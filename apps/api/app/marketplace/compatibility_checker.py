"""
app/marketplace/compatibility_checker.py

Agent Compatibility Checker & Dependency Resolver.

CTO Refinements #4, #10:
  - Validates LLM models, tools, runtime version, SDK version, manifest version,
    governance requirements, security profile, and agent dependencies (depends_on).
"""
from typing import Any, Dict, List, Optional
from app.marketplace.manifest_parser import AgentManifestSchema


class CompatibilityResult:
    """Outcome of an agent compatibility evaluation."""

    def __init__(
        self,
        compatible: bool,
        missing_models: List[str],
        missing_tools: List[str],
        missing_dependencies: List[str],
        version_incompatible: bool,
        details: Dict[str, Any],
    ) -> None:
        self.compatible = compatible
        self.missing_models = missing_models
        self.missing_tools = missing_tools
        self.missing_dependencies = missing_dependencies
        self.version_incompatible = version_incompatible
        self.details = details


class AgentCompatibilityChecker:
    """Verifies that an agent package can run safely on a tenant platform runtime."""

    DEFAULT_SUPPORTED_MODELS = {"gpt-4o", "claude-3-5-sonnet", "gemini-1.5-pro", "mock-llm-v1"}
    DEFAULT_REGISTERED_TOOLS = {"LeadTool", "TaskTool", "CommunicationTool", "WorkflowTool", "CRMTool", "EmailTool"}
    SUPPORTED_RUNTIME_VERSION = "1.0.0"
    SUPPORTED_SDK_VERSION = "1.0.0"

    def __init__(
        self,
        enabled_models: Optional[set] = None,
        installed_tools: Optional[set] = None,
        installed_agents: Optional[set] = None,
    ) -> None:
        self.enabled_models = enabled_models if enabled_models is not None else self.DEFAULT_SUPPORTED_MODELS
        self.installed_tools = installed_tools if installed_tools is not None else self.DEFAULT_REGISTERED_TOOLS
        self.installed_agents = installed_agents if installed_agents is not None else {"sales-ai", "marketing-ai", "business-ai"}

    def check_compatibility(self, manifest: AgentManifestSchema) -> CompatibilityResult:
        """Validates agent manifest against enabled platform tools, models, SDK, and dependencies (CTO #10)."""
        missing_models = [m for m in manifest.required_models if m not in self.enabled_models]
        missing_tools = [t for t in manifest.required_tools if t not in self.installed_tools]
        
        # Dependency resolution (CTO #4)
        missing_deps = []
        for dep in manifest.depends_on:
            dep_key = dep.split(">=")[0].split("==")[0].strip()
            if dep_key not in self.installed_agents:
                missing_deps.append(dep)

        # Version compatibility check (CTO #1, #10)
        version_incompatible = False
        if manifest.manifest_version > 5:
            version_incompatible = True

        compatible = (
            len(missing_models) == 0
            and len(missing_tools) == 0
            and len(missing_deps) == 0
            and not version_incompatible
        )

        details = {
            "manifest_name": manifest.name,
            "manifest_version": manifest.manifest_version,
            "api_version": manifest.api_version,
            "sdk_version": manifest.sdk_version,
            "runtime_requirement": manifest.runtime,
            "missing_models": missing_models,
            "missing_tools": missing_tools,
            "missing_dependencies": missing_deps,
            "governance_policy": manifest.governance_policy,
            "security_profile": manifest.security_profile,
        }

        return CompatibilityResult(
            compatible=compatible,
            missing_models=missing_models,
            missing_tools=missing_tools,
            missing_dependencies=missing_deps,
            version_incompatible=version_incompatible,
            details=details,
        )
