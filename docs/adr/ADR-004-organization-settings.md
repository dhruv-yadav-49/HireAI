# ADR-004: Organization Settings — Singleton Table, GET/PATCH Only

**Status**: Accepted  
**Date**: 2026-07-12  
**Sprint**: 2C

---

## Context

Every organization needs configuration: timezone, currency, language, business hours,
email signature. These settings are organization-wide, not user-specific.

## Decision

`organization_settings` is a **singleton per organization**:
- Exactly one row per organization (UNIQUE constraint on `organization_id`)
- **No `POST /settings`** endpoint — settings are created automatically on first
  `GET /settings` via `get_or_create_settings()` (idempotent)
- **Only `GET` and `PATCH`** are exposed

### `business_hours` merge semantics (day-level)

```python
# Current DB:
{"monday": {"enabled": True, "start": "09:00", "end": "17:00"}, ...}

# PATCH payload:
{"monday": {"enabled": True, "end": "19:00"}}

# Result (monday.start is gone — client must send complete day object):
{"monday": {"enabled": True, "end": "19:00"}, ...other days unchanged}
```

Day-level merge (not field-level) is chosen because:
1. Frontend sends a complete day-widget form, not partial fields
2. Field-level merge introduces ambiguity around intentional nulls

### Future extension points
- `settings_version` (integer, bump on every update) — for AI prompt cache invalidation
- `working_hours_exceptions` JSONB — holiday overrides
- `ai_persona` JSONB — AI Employee personality config

## Consequences

**Benefits:**
- No race condition on creation (idempotent `get_or_create`)
- Simple frontend contract: always GET before PATCH to get current state
- JSONB `business_hours` field can evolve without schema changes

**Trade-offs:**
- Day-level merge means clients must always send full day objects
- Documented in API description and ADR to avoid frontend confusion
