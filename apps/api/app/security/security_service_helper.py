"""
app/security/security_service_helper.py

Bridge between the existing RequestContext and the new SecurityContext.

This adapter keeps backward compatibility: existing routes continue to use
RequestContext while security components use SecurityContext.
"""
import uuid
from app.core.context import RequestContext
from app.models.enums import AuthMethod
from app.security.rbac_engine import RBACEngine
from app.security.security_context import SecurityContext, build_security_context


def build_security_ctx_from_request_ctx(ctx: RequestContext) -> SecurityContext:
    """Convert a RequestContext into a SecurityContext.

    Used by the security router and service to bridge the existing auth
    dependency chain into the new security layer without duplicating logic.
    """
    permissions = RBACEngine.permissions_as_strings(ctx.role)
    request_id = getattr(ctx, "request_id", str(uuid.uuid4()))

    return build_security_context(
        user_id=ctx.user.id,
        organization_id=ctx.organization.id,
        roles={ctx.role.value},
        permissions=permissions,
        auth_method=AuthMethod.JWT,
        request_id=request_id,
        correlation_id=request_id,
        ip_address=None,
        user_agent=None,
    )
