# ADR-003: RequestContext — Immutable Per-Request Tenant Context

**Status**: Accepted  
**Date**: 2026-07-12  
**Sprint**: 2C

---

## Context

As route handlers grow, each handler needs: the current user, their org, their role,
and the session. Without a shared structure, every handler would independently
query the DB for the same data.

## Decision

`RequestContext` is a **frozen dataclass** built once per request and cached in
`request.state.ctx`. All protected route handlers receive it via the
`get_request_context` FastAPI dependency.

```python
@dataclass(frozen=True)
class RequestContext:
    request_id: str
    request_start_time: datetime
    session: UserSession
    user: User
    organization: Organization
    membership: OrganizationMember
    role: OrganizationRole
    permissions: Optional[frozenset[str]] = None  # future permission engine

    @property
    def tenant_id(self) -> UUID: ...
    def is_owner(self) -> bool: ...
    def is_admin(self) -> bool: ...
    def can_manage_settings(self) -> bool: ...
```

### Cache strategy
```python
# build_request_context():
cached = getattr(request.state, "ctx", None)
if cached is not None:
    return cached
# ... build ctx ...
request.state.ctx = ctx
return ctx
```

## Consequences

**Benefits:**
- Single DB roundtrip per request regardless of how many deps use it
- `frozen=True` guarantees no mutation during request lifecycle
- `request_start_time` enables latency metrics and audit logging
- `permissions` field is future-ready for a granular permission engine

**Trade-offs:**
- Context is built on first use — if a route doesn't use `get_request_context`,
  no context is built (and no org validation is performed)
- Routes that need the context must explicitly declare the dependency
