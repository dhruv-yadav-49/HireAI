"""
app/governance/policy_pack_registry.py

Policy Pack Registry & Management.

CTO Refinement #5: Policy pack versioning (pack_version, published_at).
Provides pre-built enterprise policy packs:
  - HireAI.Default: General enterprise AI governance
  - HireAI.SOC2: SOC 2 compliant controls
  - HireAI.GDPR: Privacy-first rules for GDPR
  - HireAI.HIPAA: Strict healthcare controls

ADR-022: Versioned Policies — policy packs are versioned and immutable.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from app.models.enums import PolicyPackType


@dataclass(frozen=True)
class PolicyPackDefinition:
    """Immutable definition of a Governance Policy Pack."""
    pack_type: PolicyPackType
    name: str
    version: int
    published_at: str
    description: str
    rules: Dict[str, Any]


_DEFAULT_PACK = PolicyPackDefinition(
    pack_type=PolicyPackType.DEFAULT,
    name="HireAI.Default",
    version=1,
    published_at="2026-07-19T00:00:00Z",
    description="Standard enterprise AI governance pack.",
    rules={
        "permit_threshold": 0.30,
        "escalate_threshold": 0.70,
        "block_threshold": 0.85,
        "auto_approve_below": 0.20,
        "governed_actions": [
            "email_send",
            "whatsapp_send",
            "delete_lead",
            "export_data",
            "external_api",
            "crm_update",
        ],
        "approval_expires_hours": 24,
    },
)

_SOC2_PACK = PolicyPackDefinition(
    pack_type=PolicyPackType.SOC2,
    name="HireAI.SOC2",
    version=1,
    published_at="2026-07-19T00:00:00Z",
    description="SOC 2 Trust Services Criteria alignment pack.",
    rules={
        "permit_threshold": 0.20,
        "escalate_threshold": 0.50,
        "block_threshold": 0.75,
        "auto_approve_below": 0.10,
        "governed_actions": [
            "email_send",
            "whatsapp_send",
            "delete_lead",
            "export_data",
            "external_api",
            "crm_update",
            "delete_organization",
        ],
        "approval_expires_hours": 12,
        "require_dual_approval": True,
    },
)

_GDPR_PACK = PolicyPackDefinition(
    pack_type=PolicyPackType.GDPR,
    name="HireAI.GDPR",
    version=1,
    published_at="2026-07-19T00:00:00Z",
    description="GDPR privacy and data processing governance pack.",
    rules={
        "permit_threshold": 0.25,
        "escalate_threshold": 0.60,
        "block_threshold": 0.80,
        "auto_approve_below": 0.15,
        "governed_actions": [
            "email_send",
            "export_data",
            "delete_lead",
            "external_api",
        ],
        "block_unmasked_pii": True,
        "approval_expires_hours": 24,
    },
)

_HIPAA_PACK = PolicyPackDefinition(
    pack_type=PolicyPackType.HIPAA,
    name="HireAI.HIPAA",
    version=1,
    published_at="2026-07-19T00:00:00Z",
    description="HIPAA strict health data processing governance pack.",
    rules={
        "permit_threshold": 0.15,
        "escalate_threshold": 0.40,
        "block_threshold": 0.60,
        "auto_approve_below": 0.05,
        "governed_actions": [
            "email_send",
            "whatsapp_send",
            "delete_lead",
            "export_data",
            "external_api",
            "crm_update",
        ],
        "block_unmasked_pii": True,
        "approval_expires_hours": 8,
    },
)


class PolicyPackRegistry:
    """Registry managing versioned pre-built and custom policy packs."""

    def __init__(self) -> None:
        self._packs: Dict[PolicyPackType, PolicyPackDefinition] = {
            PolicyPackType.DEFAULT: _DEFAULT_PACK,
            PolicyPackType.SOC2: _SOC2_PACK,
            PolicyPackType.GDPR: _GDPR_PACK,
            PolicyPackType.HIPAA: _HIPAA_PACK,
        }

    def get_pack(self, pack_type: PolicyPackType) -> PolicyPackDefinition:
        return self._packs.get(pack_type, _DEFAULT_PACK)

    def list_packs(self) -> List[PolicyPackDefinition]:
        return list(self._packs.values())


_registry = PolicyPackRegistry()


def get_policy_pack_registry() -> PolicyPackRegistry:
    return _registry
