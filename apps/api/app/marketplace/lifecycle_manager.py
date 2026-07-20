"""
app/marketplace/lifecycle_manager.py

Agent Lifecycle State Machine Manager.

CTO Refinements #5, #7, #8:
  - Enforces valid state transitions:
    DRAFT -> SANDBOX_TESTED -> SECURITY_CHECKED -> GOVERNANCE_CHECKED -> PUBLISHED -> INSTALLED -> VERIFIED -> ENABLED -> DISABLED -> ARCHIVED
  - Manages installation verification and version rollback tracking.
"""
from typing import Dict, Set
from app.models.enums import AgentLifecycleStatus, AgentInstallationStatus


class AgentLifecycleManager:
    """Enforces state transitions and lifecycle validation for marketplace agents."""

    VALID_PACKAGE_TRANSITIONS: Dict[AgentLifecycleStatus, Set[AgentLifecycleStatus]] = {
        AgentLifecycleStatus.DRAFT: {AgentLifecycleStatus.SANDBOX_TESTED, AgentLifecycleStatus.ARCHIVED},
        AgentLifecycleStatus.SANDBOX_TESTED: {AgentLifecycleStatus.SECURITY_CHECKED, AgentLifecycleStatus.ARCHIVED},
        AgentLifecycleStatus.SECURITY_CHECKED: {AgentLifecycleStatus.GOVERNANCE_CHECKED, AgentLifecycleStatus.ARCHIVED},
        AgentLifecycleStatus.GOVERNANCE_CHECKED: {AgentLifecycleStatus.PUBLISHED, AgentLifecycleStatus.ARCHIVED},
        AgentLifecycleStatus.PUBLISHED: {AgentLifecycleStatus.INSTALLED, AgentLifecycleStatus.ARCHIVED},
        AgentLifecycleStatus.INSTALLED: {AgentLifecycleStatus.ENABLED, AgentLifecycleStatus.DISABLED, AgentLifecycleStatus.ARCHIVED},
        AgentLifecycleStatus.ENABLED: {AgentLifecycleStatus.DISABLED, AgentLifecycleStatus.ARCHIVED},
        AgentLifecycleStatus.DISABLED: {AgentLifecycleStatus.ENABLED, AgentLifecycleStatus.ARCHIVED},
        AgentLifecycleStatus.ARCHIVED: set(),
    }

    VALID_INSTALLATION_TRANSITIONS: Dict[AgentInstallationStatus, Set[AgentInstallationStatus]] = {
        AgentInstallationStatus.PENDING: {AgentInstallationStatus.INSTALLED, AgentInstallationStatus.FAILED},
        AgentInstallationStatus.INSTALLED: {AgentInstallationStatus.VERIFIED, AgentInstallationStatus.FAILED},
        AgentInstallationStatus.VERIFIED: {AgentInstallationStatus.ACTIVE, AgentInstallationStatus.FAILED},
        AgentInstallationStatus.ACTIVE: {AgentInstallationStatus.UNINSTALLED, AgentInstallationStatus.FAILED},
        AgentInstallationStatus.FAILED: {AgentInstallationStatus.PENDING, AgentInstallationStatus.UNINSTALLED},
        AgentInstallationStatus.UNINSTALLED: set(),
    }

    @classmethod
    def can_transition_package(cls, current: AgentLifecycleStatus, target: AgentLifecycleStatus) -> bool:
        """Verifies if package status transition is valid."""
        allowed = cls.VALID_PACKAGE_TRANSITIONS.get(current, set())
        return target in allowed

    @classmethod
    def can_transition_installation(cls, current: AgentInstallationStatus, target: AgentInstallationStatus) -> bool:
        """Verifies if installation status transition is valid."""
        allowed = cls.VALID_INSTALLATION_TRANSITIONS.get(current, set())
        return target in allowed
