# ADR-002: Multi-Tenant Architecture — Membership-Based Tenancy

**Status**: Accepted  
**Date**: 2026-07-12  
**Sprint**: 2A (formalized in 2C)

---

## Context

HireAI is a multi-tenant SaaS platform. Users can belong to multiple organizations.
An early model had `user.org_id` as a foreign key — simple but wrong.

## Decision

**No `org_id` on the `User` table.**

Tenancy is managed exclusively through `OrganizationMember`:

```
User ──< OrganizationMember >── Organization
           (role, status)
```

- A user can have **multiple** memberships (one per org they belong to)
- Current active org is tracked **per session** in `UserSession.active_organization_id`
- This allows each device to be in a different org simultaneously
- Role is per-membership, not per-user

## Consequences

**Benefits:**
- Supports multi-org users natively (no schema changes needed)
- Per-device org context enables true multi-tenancy UX
- Role management is org-scoped, not user-global

**Trade-offs:**
- Every request must JOIN through OrganizationMember to get role/org
- Mitigated by `RequestContext` caching (one resolution per request)
