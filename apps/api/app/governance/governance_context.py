"""
app/governance/governance_context.py

Immutable GovernanceContext object.

CTO Refinement #1: Just like Sprint 7C introduced SecurityContext, Sprint 7D
introduces an immutable GovernanceContext passed throughout all governance modules.

ADR-022: Governance by Composition — GovernanceContext wraps SecurityContext and
adds AI action metadata without modifying Runtime or Security layers.
"""
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from app.security.security_context import SecurityContext


@dataclass(frozen=True)
class GovernanceContext:
    """Immutable execution context for AI governance decisions.

    Composes SecurityContext (identity, tenant, roles) with AI action metadata.
    """
    security_context: SecurityContext

    # Action Target Metadata
    action_type: str                  # e.g. "email_send", "delete_lead", "export_data"
    job_type: Optional[str] = None    # e.g. "SALES_OUTREACH", "MARKETING_CAMPAIGN"
    agent_type: Optional[str] = None  # e.g. "SALES_AGENT", "EXECUTIVE_AGENT"
    resource_type: Optional[str] = None # e.g. "Lead", "Workflow", "Organization"

    # Action Inputs & Attributes for Risk Analysis & ABAC
    action_payload: Dict[str, Any] = field(default_factory=dict)
    resource_attrs: Dict[str, Any] = field(default_factory=dict)
    risk_inputs: Dict[str, Any] = field(default_factory=dict)

    # Identifiers
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def organization_id(self) -> uuid.UUID:
        return self.security_context.organization_id

    @property
    def user_id(self) -> uuid.UUID:
        return self.security_context.user_id

    def cache_key(self) -> str:
        """Deterministically generate cache key for decision caching."""
        import hashlib
        import json
        payload_str = json.dumps(self.action_payload, sort_keys=True, default=str)
        payload_hash = hashlib.sha256(payload_str.encode()).hexdigest()[:16]
        return f"{self.organization_id}:{self.action_type}:{payload_hash}"


def build_governance_context(
    security_context: SecurityContext,
    action_type: str,
    action_payload: Optional[Dict[str, Any]] = None,
    job_type: Optional[str] = None,
    agent_type: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_attrs: Optional[Dict[str, Any]] = None,
    risk_inputs: Optional[Dict[str, Any]] = None,
) -> GovernanceContext:
    """Factory builder for GovernanceContext."""
    return GovernanceContext(
        security_context=security_context,
        action_type=action_type,
        job_type=job_type,
        agent_type=agent_type,
        resource_type=resource_type,
        action_payload=action_payload or {},
        resource_attrs=resource_attrs or {},
        risk_inputs=risk_inputs or {},
        request_id=security_context.request_id,
        correlation_id=security_context.correlation_id,
    )
