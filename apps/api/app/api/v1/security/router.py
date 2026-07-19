"""
app/api/v1/security/router.py

Enterprise Security REST API — 12 endpoints.

All endpoints require JWT authentication via get_request_context().
Admin-only endpoints additionally check ctx.is_admin().
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_request_context, get_db
from app.core.context import RequestContext
from app.db.session import get_db
from app.repositories.security_repository import SecurityRepository
from app.security.oidc_service import OIDCService
from app.security.pii_detector import get_pii_detector
from app.security.pii_masker import PIIMasker
from app.security.security_context import build_security_context
from app.security.security_service_helper import build_security_ctx_from_request_ctx
from app.services.security_service import SecurityService
from app.models.enums import AuthMethod

router = APIRouter(prefix="/security", tags=["Security"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class CreateAPIKeyRequest(BaseModel):
    name: str
    scopes: List[str] = ["*"]
    expires_at: Optional[datetime] = None
    created_from: Optional[str] = None


class CreateAPIKeyResponse(BaseModel):
    id: str
    raw_key: str          # Shown ONCE — store it securely
    prefix: str
    name: str
    scopes: List[str]
    expires_at: Optional[datetime]
    message: str = "Store this key securely. It will not be shown again."


class APIKeyListItem(BaseModel):
    id: str
    name: str
    prefix: str
    scopes: List[str]
    status: str
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_from: Optional[str]
    created_at: datetime


class PIIScanRequest(BaseModel):
    text: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


class PIIScanResponse(BaseModel):
    matches: int
    types_found: List[str]
    masked_text: Optional[str] = None
    masked_payload: Optional[Dict[str, Any]] = None


class AuthorizeRequest(BaseModel):
    resource_type: str
    action: str
    resource_attrs: Optional[Dict[str, Any]] = None


class AuthorizeResponse(BaseModel):
    allowed: bool
    reason: str
    cached: bool


# ── API Key Endpoints ──────────────────────────────────────────────────────────

@router.post("/api-keys", response_model=CreateAPIKeyResponse)
async def create_api_key(
    body: CreateAPIKeyRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """Create a scoped API key for the current organization."""
    if not ctx.is_admin():
        raise HTTPException(403, "Only admins can create API keys.")

    svc = SecurityService(db)
    sec_ctx = build_security_ctx_from_request_ctx(ctx)
    raw_key, key_record = await svc.create_api_key(
        ctx=sec_ctx,
        name=body.name,
        scopes=body.scopes,
        expires_at=body.expires_at,
        created_from=body.created_from,
    )
    await db.commit()

    return CreateAPIKeyResponse(
        id=str(key_record.id),
        raw_key=raw_key,
        prefix=key_record.prefix,
        name=key_record.name,
        scopes=key_record.scopes_json,
        expires_at=key_record.expires_at,
    )


@router.get("/api-keys", response_model=List[APIKeyListItem])
async def list_api_keys(
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """List all active API keys for the current organization."""
    repo = SecurityRepository(db)
    keys = await repo.list_api_keys(ctx.tenant_id)
    return [
        APIKeyListItem(
            id=str(k.id),
            name=k.name,
            prefix=k.prefix,
            scopes=k.scopes_json or [],
            status=k.status.value,
            last_used_at=k.last_used_at,
            expires_at=k.expires_at,
            created_from=k.created_from,
            created_at=k.created_at,
        )
        for k in keys
    ]


@router.delete("/api-keys/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """Revoke an API key permanently."""
    if not ctx.is_admin():
        raise HTTPException(403, "Only admins can revoke API keys.")

    svc = SecurityService(db)
    sec_ctx = build_security_ctx_from_request_ctx(ctx)
    await svc.revoke_api_key(sec_ctx, key_id)
    await db.commit()


@router.post("/api-keys/{key_id}/rotate", response_model=CreateAPIKeyResponse)
async def rotate_api_key(
    key_id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """Rotate an API key — revokes old key and issues a new one with same scopes."""
    if not ctx.is_admin():
        raise HTTPException(403, "Only admins can rotate API keys.")

    svc = SecurityService(db)
    sec_ctx = build_security_ctx_from_request_ctx(ctx)
    raw_key, new_key = await svc.rotate_api_key(sec_ctx, key_id)
    await db.commit()

    return CreateAPIKeyResponse(
        id=str(new_key.id),
        raw_key=raw_key,
        prefix=new_key.prefix,
        name=new_key.name,
        scopes=new_key.scopes_json,
        expires_at=new_key.expires_at,
    )


# ── Audit Log Endpoints ────────────────────────────────────────────────────────

@router.get("/audit")
async def get_audit_log(
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """Paginated audit log for the current organization."""
    repo = SecurityRepository(db)
    logs = await repo.list_audit_logs(ctx.tenant_id, limit=limit, offset=offset)
    return [
        {
            "id": str(log.id),
            "action": log.action.value,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "success": log.success,
            "duration_ms": log.duration_ms,
            "request_id": log.request_id,
            "correlation_id": log.correlation_id,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]


# ── Security Policy Endpoints ──────────────────────────────────────────────────

@router.get("/policies")
async def list_security_policies(
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """List security policies for the current organization."""
    if not ctx.is_admin():
        raise HTTPException(403, "Only admins can view security policies.")
    repo = SecurityRepository(db)
    policies = await repo.list_security_policies(ctx.tenant_id)
    return [
        {
            "id": str(p.id),
            "policy_name": p.policy_name,
            "rules": p.rules_json,
            "enabled": p.enabled,
            "status": p.status.value,
            "created_at": p.created_at.isoformat(),
        }
        for p in policies
    ]


@router.put("/policies/{policy_id}")
async def update_security_policy(
    policy_id: uuid.UUID,
    body: Dict[str, Any],
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """Update a security policy's rules."""
    if not ctx.is_owner():
        raise HTTPException(403, "Only owners can update security policies.")
    repo = SecurityRepository(db)
    policy = await repo.upsert_security_policy(
        org_id=ctx.tenant_id,
        policy_name=body.get("policy_name", "Custom Policy"),
        rules=body.get("rules", {}),
    )
    await db.commit()
    return {"id": str(policy.id), "updated": True}


# ── PII Endpoints ──────────────────────────────────────────────────────────────

@router.get("/pii")
async def list_pii_incidents(
    limit: int = Query(100, le=500),
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """List PII detection incidents for the current organization."""
    if not ctx.is_admin():
        raise HTTPException(403, "Only admins can view PII incidents.")
    repo = SecurityRepository(db)
    incidents = await repo.list_pii_incidents(ctx.tenant_id, limit=limit)
    return [
        {
            "id": str(i.id),
            "pii_type": i.pii_type.value,
            "location": i.location,
            "severity": i.severity,
            "confidence": i.confidence,
            "masked": i.masked,
            "created_at": i.created_at.isoformat(),
        }
        for i in incidents
    ]


@router.post("/pii/scan", response_model=PIIScanResponse)
async def scan_pii(
    body: PIIScanRequest,
    ctx: RequestContext = Depends(get_request_context),
):
    """Scan text or a JSON payload for PII. Does not persist results."""
    detector = get_pii_detector()
    matches = []

    if body.text:
        matches = detector.scan(body.text)
        masked_text = PIIMasker.mask(body.text, matches) if matches else body.text
        return PIIScanResponse(
            matches=len(matches),
            types_found=list({m.pii_type.value for m in matches}),
            masked_text=masked_text,
        )

    if body.payload:
        matches = detector.scan_dict(body.payload)
        masked_payload = PIIMasker.mask_dict(body.payload, matches) if matches else body.payload
        return PIIScanResponse(
            matches=len(matches),
            types_found=list({m.pii_type.value for m in matches}),
            masked_payload=masked_payload,
        )

    return PIIScanResponse(matches=0, types_found=[])


# ── Authorization Test Endpoint ────────────────────────────────────────────────

@router.post("/authorize", response_model=AuthorizeResponse)
async def test_authorization(
    body: AuthorizeRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """Test an authorization decision for the current user (dry-run)."""
    svc = SecurityService(db)
    sec_ctx = build_security_ctx_from_request_ctx(ctx)
    decision = await svc.authorize(
        ctx=sec_ctx,
        resource_type=body.resource_type,
        action=body.action,
        resource_attrs=body.resource_attrs,
    )
    return AuthorizeResponse(
        allowed=decision.allowed,
        reason=decision.reason,
        cached=decision.cached,
    )


# ── Secret References ──────────────────────────────────────────────────────────

@router.get("/secrets")
async def list_secret_references(
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    """List secret reference metadata (never values) for the organization."""
    if not ctx.is_admin():
        raise HTTPException(403, "Only admins can list secrets.")
    repo = SecurityRepository(db)
    refs = await repo.list_secret_references(ctx.tenant_id)
    return [
        {
            "id": str(r.id),
            "secret_name": r.secret_name,
            "secret_type": r.secret_type.value,
            "provider": r.provider,
            "rotation_period_days": r.rotation_period_days,
            "last_rotated_at": r.last_rotated_at.isoformat() if r.last_rotated_at else None,
            "created_at": r.created_at.isoformat(),
        }
        for r in refs
    ]


# ── OIDC Discovery ─────────────────────────────────────────────────────────────

@router.get("/oidc/discovery", include_in_schema=True)
async def oidc_discovery():
    """OpenID Connect Discovery document."""
    return OIDCService.discovery_document()
