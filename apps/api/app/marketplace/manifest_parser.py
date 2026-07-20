"""
app/marketplace/manifest_parser.py

Agent Manifest Parser & Standardized Schema Validator.

CTO Refinements #1, #3:
  - Versioned independently: manifest_version (1), api_version ("1.0"), sdk_version (">=1.0")
  - Standardized schema: name, display_name, description, version, runtime, entrypoint,
    permissions, required_tools, required_models, required_events, required_memory,
    supported_languages, governance_policy, security_profile, depends_on, icon, license
"""
import yaml
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class AgentManifestSchema(BaseModel):
    """Standardized schema contract between marketplace developers and runtime (CTO #1, #3)."""

    name: str = Field(..., min_length=2, max_length=100)
    display_name: str = Field(..., min_length=2, max_length=100)
    description: str = Field(..., min_length=5, max_length=2000)
    version: str = Field(..., min_length=1, max_length=50)

    manifest_version: int = Field(default=1, ge=1)
    api_version: str = Field(default="1.0")
    sdk_version: str = Field(default=">=1.0")
    runtime: str = Field(default=">=1.0")

    entrypoint: str = Field(default="agent.py")
    permissions: List[str] = Field(default_factory=list)
    required_tools: List[str] = Field(default_factory=list)
    required_models: List[str] = Field(default_factory=list)
    required_events: List[str] = Field(default_factory=list)
    required_memory: List[str] = Field(default_factory=list)
    depends_on: List[str] = Field(default_factory=list)  # CTO #4: Agent dependencies

    supported_languages: List[str] = Field(default_factory=lambda: ["en"])
    governance_policy: str = Field(default="DEFAULT")
    security_profile: str = Field(default="STANDARD")

    icon: Optional[str] = Field(default="icon.png")
    license: Optional[str] = Field(default="MIT")

    @field_validator("name")
    @classmethod
    def validate_name_slug(cls, v: str) -> str:
        if " " in v or not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Agent name must be a valid slug (e.g. 'sales-ai', 'recruiter-ai').")
        return v.lower()


class AgentManifestParser:
    """Parses and validates raw YAML/dict manifests against standard AgentManifestSchema."""

    @classmethod
    def parse_yaml(cls, raw_yaml: str) -> AgentManifestSchema:
        """Parses raw YAML text string into validated AgentManifestSchema."""
        try:
            parsed_dict = yaml.safe_load(raw_yaml)
            if not isinstance(parsed_dict, dict):
                raise ValueError("Manifest content must be a valid YAML object key-value dictionary.")
            return cls.parse_dict(parsed_dict)
        except Exception as exc:
            raise ValueError(f"Manifest Parsing Error: {str(exc)}")

    @classmethod
    def parse_dict(cls, raw_dict: Dict[str, Any]) -> AgentManifestSchema:
        """Validates raw dictionary into AgentManifestSchema."""
        return AgentManifestSchema(**raw_dict)
