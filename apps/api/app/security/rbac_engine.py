"""
app/security/rbac_engine.py

Resource-Level Role-Based Access Control.

Evolves the existing OrganizationRole enum into fine-grained
(resource_type, action) permission pairs. The existing is_admin() /
is_owner() helpers on RequestContext remain fully functional — this
engine layers on top.

ADR-021: Least Privilege — access is granted only to the minimum
required resources.
"""
from dataclasses import dataclass
from typing import FrozenSet, Dict

from app.models.enums import OrganizationRole


@dataclass(frozen=True)
class ResourcePermission:
    """A single permission: (resource_type, action).

    Examples:
        ResourcePermission("Lead", "read")
        ResourcePermission("Lead", "delete")
        ResourcePermission("APIKey", "create")
    """
    resource_type: str
    action: str

    def __str__(self) -> str:
        return f"{self.resource_type}:{self.action}"


def _p(resource: str, action: str) -> ResourcePermission:
    return ResourcePermission(resource, action)


# ── Permission map ─────────────────────────────────────────────────────────────
# Each role is granted a frozenset of resource-level permissions.
# Higher roles include all permissions of lower roles.

_MEMBER_PERMISSIONS: FrozenSet[ResourcePermission] = frozenset({
    _p("Lead", "read"),
    _p("Task", "read"),
    _p("Workflow", "read"),
    _p("AuditLog", "read"),
})

_SALES_PERMISSIONS: FrozenSet[ResourcePermission] = _MEMBER_PERMISSIONS | frozenset({
    _p("Lead", "create"),
    _p("Lead", "update"),
    _p("Task", "create"),
    _p("Task", "update"),
    _p("Communication", "create"),
    _p("AIJob", "create"),
    _p("AIJob", "read"),
})

_ADMIN_PERMISSIONS: FrozenSet[ResourcePermission] = _SALES_PERMISSIONS | frozenset({
    _p("Lead", "delete"),
    _p("Task", "delete"),
    _p("Workflow", "create"),
    _p("Workflow", "update"),
    _p("Workflow", "delete"),
    _p("APIKey", "create"),
    _p("APIKey", "read"),
    _p("APIKey", "revoke"),
    _p("SecurityPolicy", "read"),
    _p("SecurityPolicy", "update"),
    _p("PIIIncident", "read"),
    _p("SecretReference", "create"),
    _p("SecretReference", "read"),
})

_OWNER_PERMISSIONS: FrozenSet[ResourcePermission] = _ADMIN_PERMISSIONS | frozenset({
    _p("APIKey", "rotate"),
    _p("APIKey", "delete"),
    _p("SecurityPolicy", "create"),
    _p("SecurityPolicy", "delete"),
    _p("SecretReference", "delete"),
    _p("Organization", "update"),
    _p("Organization", "delete"),
    _p("OrganizationMember", "invite"),
    _p("OrganizationMember", "remove"),
    _p("OrganizationMember", "update_role"),
})

ROLE_PERMISSION_MAP: Dict[OrganizationRole, FrozenSet[ResourcePermission]] = {
    OrganizationRole.OWNER: _OWNER_PERMISSIONS,
    OrganizationRole.ADMIN: _ADMIN_PERMISSIONS,
    OrganizationRole.SALES: _SALES_PERMISSIONS,
    OrganizationRole.VIEWER: _MEMBER_PERMISSIONS,
}


class RBACEngine:
    """Stateless RBAC evaluation engine."""

    @staticmethod
    def get_permissions(role: OrganizationRole) -> FrozenSet[ResourcePermission]:
        """Return all permissions for a given role."""
        return ROLE_PERMISSION_MAP.get(role, frozenset())

    @staticmethod
    def check_permission(
        role: OrganizationRole,
        resource_type: str,
        action: str,
    ) -> bool:
        """Return True if the role has the given (resource_type, action) permission."""
        perms = RBACEngine.get_permissions(role)
        target = ResourcePermission(resource_type, action)
        # Exact match
        if target in perms:
            return True
        # Wildcard action: "*" on this resource_type
        if ResourcePermission(resource_type, "*") in perms:
            return True
        return False

    @staticmethod
    def permissions_as_strings(role: OrganizationRole) -> FrozenSet[str]:
        """Return permissions as 'ResourceType:action' strings for SecurityContext."""
        return frozenset(str(p) for p in RBACEngine.get_permissions(role))
