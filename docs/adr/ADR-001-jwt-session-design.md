# ADR-001: JWT Session Design — No Role or Org in Token

**Status**: Accepted  
**Date**: 2026-07-12  
**Sprint**: 2C

---

## Context

During Sprint 1, the JWT payload included `role` and `org` claims for convenience.
In Sprint 2C, we introduced per-session organization switching. This revealed a
critical flaw: if a user's role is changed (e.g., ADMIN → SALES), existing tokens
continue to carry the old `role` claim for up to 15 minutes.

## Decision

The JWT access token payload contains **only**:

```json
{
  "sub": "<user_id>",
  "sid": "<session_id>",
  "type": "access",
  "jti": "<unique token id>",
  "iat": "<issued at>",
  "exp": "<expiry>"
}
```

`role` and `org` are **explicitly excluded**. They are resolved at runtime from:
- `role` → `OrganizationMember.role` via `RequestContext.membership`
- `org` → `UserSession.active_organization_id` via the `sid` claim

## Consequences

**Benefits:**
- Role changes take effect on the very next request (zero staleness)
- Organization switches affect only the session, not the token
- Reduced token payload size

**Trade-offs:**
- Every authenticated request resolves the session + membership from DB
- Mitigated by `request.state.ctx` caching (one DB roundtrip per request, not per dependency)
