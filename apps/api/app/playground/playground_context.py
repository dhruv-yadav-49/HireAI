"""
app/playground/playground_context.py

Immutable PlaygroundContext object.

CTO Refinement #1: Composes SecurityContext and GovernanceContext into a unified
context for all playground DX components.

ADR-023: Session Isolation & Unified DX.
"""
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from app.governance.governance_context import GovernanceContext
from app.models.enums import AIProvider, SandboxIsolationLevel
from app.security.security_context import SecurityContext


@dataclass(frozen=True)
class PlaygroundContext:
    """Immutable execution context for developer playground experimentation."""

    security_context: SecurityContext
    governance_context: Optional[GovernanceContext] = None

    session_id: uuid.UUID = field(default_factory=uuid.uuid4)
    sandbox_id: uuid.UUID = field(default_factory=uuid.uuid4)
    experiment_id: Optional[uuid.UUID] = None

    provider: AIProvider = AIProvider.MOCK
    model_name: str = "mock-llm-v1"
    temperature: float = 0.7
    max_tokens: int = 1000

    isolation_level: SandboxIsolationLevel = SandboxIsolationLevel.READ_ONLY

    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def organization_id(self) -> uuid.UUID:
        return self.security_context.organization_id

    @property
    def user_id(self) -> uuid.UUID:
        return self.security_context.user_id


def build_playground_context(
    security_context: SecurityContext,
    session_id: Optional[uuid.UUID] = None,
    experiment_id: Optional[uuid.UUID] = None,
    governance_context: Optional[GovernanceContext] = None,
    provider: AIProvider = AIProvider.MOCK,
    model_name: str = "mock-llm-v1",
    temperature: float = 0.7,
    max_tokens: int = 1000,
    isolation_level: SandboxIsolationLevel = SandboxIsolationLevel.READ_ONLY,
) -> PlaygroundContext:
    """Factory builder for PlaygroundContext."""
    return PlaygroundContext(
        security_context=security_context,
        governance_context=governance_context,
        session_id=session_id or uuid.uuid4(),
        experiment_id=experiment_id,
        provider=provider,
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        isolation_level=isolation_level,
        correlation_id=security_context.correlation_id,
    )
