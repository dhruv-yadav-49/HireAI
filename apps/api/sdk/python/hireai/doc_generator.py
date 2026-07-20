"""
hireai.sdk.doc_generator — Agent Documentation Generator Module.

CTO Refinement #9:
  Automatically generates clean Markdown & HTML documentation pages directly from agent manifests.
"""
from typing import Any, Dict


class AgentDocGenerator:
    """Generates Markdown & HTML documentation pages for agents (CTO #9)."""

    @classmethod
    def generate_markdown(cls, manifest_dict: Dict[str, Any]) -> str:
        """Generates clean GitHub-style Markdown documentation."""
        name = manifest_dict.get("display_name", manifest_dict.get("name", "Agent"))
        version = manifest_dict.get("version", "1.0.0")
        desc = manifest_dict.get("description", "No description provided.")
        permissions = manifest_dict.get("permissions", [])
        tools = manifest_dict.get("required_tools", [])
        models = manifest_dict.get("required_models", [])
        depends_on = manifest_dict.get("depends_on", [])

        md = []
        md.append(f"# {name} (v{version})")
        md.append(f"\n{desc}\n")
        md.append("## Required Permissions")
        if permissions:
            for p in permissions:
                md.append(f"- `{p}`")
        else:
            md.append("- None")

        md.append("\n## Required Platform Tools")
        if tools:
            for t in tools:
                md.append(f"- `{t}`")
        else:
            md.append("- None")

        md.append("\n## Required LLM Models")
        if models:
            for m in models:
                md.append(f"- `{m}`")
        else:
            md.append("- None")

        md.append("\n## Agent Dependencies")
        if depends_on:
            for d in depends_on:
                md.append(f"- `{d}`")
        else:
            md.append("- None")

        return "\n".join(md)

    @classmethod
    def generate_html(cls, manifest_dict: Dict[str, Any]) -> str:
        """Generates responsive HTML documentation snippet."""
        md = cls.generate_markdown(manifest_dict)
        return f"<div class='hireai-doc'>\n<pre>{md}</pre>\n</div>"
