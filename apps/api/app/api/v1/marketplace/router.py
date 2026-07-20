"""
app/api/v1/marketplace/router.py

Agent Marketplace Platform Infrastructure Endpoints (Sprint 8A).
Exposes package uploads, validation pipelines, compatibility checks, installation, verification, loading, and rollbacks.
"""
import uuid
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.security.security_context import SecurityContext, get_current_security_context
from app.services.marketplace_service import MarketplaceService

router = APIRouter(prefix="/marketplace", tags=["Agent Marketplace Platform"])


@router.post(
    "/packages/upload",
    summary="Upload Agent Package Manifest",
    description="Uploads a raw .hireagent package manifest (YAML/JSON) into the platform marketplace registry.",
)
async def upload_package(
    raw_manifest_yaml: str = Body(..., media_type="text/plain"),
    author: str = "Official Platform",
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    service = MarketplaceService(db)
    pkg = await service.upload_package(raw_manifest_yaml, author=author)
    return {
        "id": str(pkg.id),
        "package_name": pkg.package_name,
        "display_name": pkg.display_name,
        "version": pkg.version,
        "lifecycle_status": pkg.lifecycle_status.value,
        "package_hash": pkg.package_hash,
    }


@router.post(
    "/packages/{package_id}/validate",
    summary="Run Automated Validation Pipeline",
    description="Executes the explicit 6-stage validation scanner (Manifest -> Integrity -> Sandbox -> Security -> Governance -> Compatibility).",
)
async def validate_package(
    package_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    service = MarketplaceService(db)
    try:
        return await service.validate_package(package_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/packages/{package_id}/check-compatibility",
    summary="Check Tenant Compatibility",
    description="Validates agent package requirement compatibility against current tenant models, tools, and permissions.",
)
async def check_compatibility(
    package_id: uuid.UUID,
    sec_ctx: SecurityContext = Depends(get_current_security_context),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    service = MarketplaceService(db)
    try:
        return await service.check_compatibility(sec_ctx, package_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/packages/{package_id}/install",
    summary="Install & Verify Agent Package",
    description="Executes tenant installation sequence: Install -> Verify -> Enable.",
)
async def install_package(
    package_id: uuid.UUID,
    sec_ctx: SecurityContext = Depends(get_current_security_context),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    service = MarketplaceService(db)
    try:
        inst = await service.install_package(sec_ctx, package_id)
        return {
            "installation_id": str(inst.id),
            "organization_id": str(inst.organization_id),
            "agent_key": inst.agent_key,
            "current_version": inst.current_version,
            "previous_version": inst.previous_version,
            "status": inst.status.value,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/installations/{installation_id}/rollback",
    summary="Rollback Agent Installation",
    description="Rolls back tenant agent installation to previous version.",
)
async def rollback_installation(
    installation_id: uuid.UUID,
    sec_ctx: SecurityContext = Depends(get_current_security_context),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    service = MarketplaceService(db)
    try:
        inst = await service.rollback_installation(sec_ctx, installation_id)
        return {
            "installation_id": str(inst.id),
            "agent_key": inst.agent_key,
            "current_version": inst.current_version,
            "status": inst.status.value,
            "message": f"Successfully rolled back agent '{inst.agent_key}' to v{inst.current_version}.",
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get(
    "/installations",
    summary="List Tenant Agent Installations",
    description="Lists all active agent installations for current tenant organization.",
)
async def list_installations(
    sec_ctx: SecurityContext = Depends(get_current_security_context),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    service = MarketplaceService(db)
    insts = await service.repo.list_installations(sec_ctx.organization_id)
    return [
        {
            "id": str(i.id),
            "agent_key": i.agent_key,
            "current_version": i.current_version,
            "previous_version": i.previous_version,
            "status": i.status.value,
            "installed_at": i.installed_at.isoformat(),
        }
        for i in insts
    ]
