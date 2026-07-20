"""
app/marketplace/installation_preview.py

Rich Explainable Installation Preview Generator.

CTO Refinement #3:
  Produces detailed, explainable breakdown of tools, models, permissions,
  and dependent agent status instead of a simple pass/fail flag.
"""
from typing import Any, Dict, List, Set
from app.marketplace.manifest_parser import AgentManifestSchema
from app.marketplace.marketplace_resolver import InstallationPlan


class DependencyRequirementStatus:
    def __init__(self, item_name: str, item_type: str, status: str, detail: str) -> None:
        self.item_name = item_name
        self.item_type = item_type
        self.status = status  # "INSTALLED_OK", "MISSING_ERROR", "AVAILABLE"
        self.detail = detail


class RichInstallationPreview:
    """Generates human-readable, explainable installation previews (CTO #3)."""

    @classmethod
    def generate_preview(
        cls,
        manifest: AgentManifestSchema,
        plan: InstallationPlan,
        tenant_models: Set[str],
        tenant_tools: Set[str],
        installed_agents: Set[str],
    ) -> Dict[str, Any]:
        requirements: List[DependencyRequirementStatus] = []

        # 1. Tools Check
        for tool in manifest.required_tools:
            if tool in tenant_tools:
                requirements.append(DependencyRequirementStatus(tool, "TOOL", "INSTALLED_OK", "Tool is available in system."))
            else:
                requirements.append(DependencyRequirementStatus(tool, "TOOL", "MISSING_ERROR", "Tool missing from tenant tool registry."))

        # 2. Models Check
        for model in manifest.required_models:
            if model in tenant_models:
                requirements.append(DependencyRequirementStatus(model, "MODEL", "INSTALLED_OK", "LLM Model provider licensed."))
            else:
                requirements.append(DependencyRequirementStatus(model, "MODEL", "MISSING_ERROR", "LLM Model provider not licensed/enabled."))

        # 3. Agent Dependencies Check
        for agent_dep in plan.installation_order:
            if agent_dep == manifest.name:
                continue
            if agent_dep in installed_agents:
                requirements.append(DependencyRequirementStatus(agent_dep, "AGENT", "INSTALLED_OK", f"Dependent agent '{agent_dep}' installed."))
            else:
                requirements.append(DependencyRequirementStatus(agent_dep, "AGENT", "WILL_INSTALL", f"Dependent agent '{agent_dep}' will be automatically installed."))

        missing_count = sum(1 for req in requirements if req.status == "MISSING_ERROR")
        ready_to_install = missing_count == 0 and plan.executable

        return {
            "agent_name": manifest.name,
            "agent_version": manifest.version,
            "ready_to_install": ready_to_install,
            "executable_plan": plan.executable,
            "installation_order": plan.installation_order,
            "block_reasons": plan.block_reasons,
            "requirements_breakdown": [
                {
                    "item_name": r.item_name,
                    "item_type": r.item_type,
                    "status": r.status,
                    "detail": r.detail,
                }
                for r in requirements
            ],
        }
