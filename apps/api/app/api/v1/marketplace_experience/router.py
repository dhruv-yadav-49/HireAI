"""
app/api/v1/marketplace_experience/router.py

Agent Marketplace Experience & Resolver API Endpoints (Sprint 8B).
Exposes Catalog browsing, Search & Discovery, Installation Preview Wizard, Publishing Workflows, Reviews, Analytics Dashboard, and Publisher Profiles.
"""
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.security.security_context import SecurityContext, get_current_security_context
from app.services.marketplace_experience_service import MarketplaceExperienceService
from app.models.enums import ReleaseChannel

router = APIRouter(prefix="/marketplace", tags=["Agent Marketplace Experience"])


@router.get(
    "/catalog",
    summary="Browse Marketplace Catalog",
    description="Browse published agent catalog with ratings and categories.",
)
async def get_catalog(
    category: Optional[str] = None,
    featured_only: bool = False,
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    service = MarketplaceExperienceService(db)
    return await service.get_catalog(category=category, featured_only=featured_only)


@router.get(
    "/search",
    summary="Search & Filter Agents",
    description="Full-text keyword search and filtering across published agent packages.",
)
async def search_catalog(
    q: Optional[str] = Query(None, description="Search keyword"),
    author: Optional[str] = Query(None, description="Publisher author filter"),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    service = MarketplaceExperienceService(db)
    return await service.search_catalog(query=q, author=author)


@router.post(
    "/preview-installation",
    summary="Installation Wizard & Dependency Preview",
    description="Generates an explainable installation preview using MarketplaceResolver to evaluate tools, models, and dependencies.",
)
async def preview_installation(
    package_id: uuid.UUID,
    sec_ctx: SecurityContext = Depends(get_current_security_context),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    service = MarketplaceExperienceService(db)
    try:
        return await service.preview_installation(sec_ctx, package_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/packages/{package_id}/publish",
    summary="Publish Agent Package Release",
    description="Executes publishing workflow (Draft -> Published) and records release history.",
)
async def publish_package(
    package_id: uuid.UUID,
    channel: ReleaseChannel = ReleaseChannel.STABLE,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    service = MarketplaceExperienceService(db)
    try:
        pkg = await service.publish_package(package_id, channel=channel)
        return {
            "id": str(pkg.id),
            "package_name": pkg.package_name,
            "version": pkg.version,
            "lifecycle_status": pkg.lifecycle_status.value,
            "message": f"Package '{pkg.package_name}' successfully published on channel '{channel.value}'.",
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/packages/{package_id}/deprecate",
    summary="Deprecate Package Release",
    description="Deprecates a published package release version.",
)
async def deprecate_package(
    package_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    service = MarketplaceExperienceService(db)
    try:
        pkg = await service.deprecate_package(package_id)
        return {
            "id": str(pkg.id),
            "package_name": pkg.package_name,
            "lifecycle_status": pkg.lifecycle_status.value,
            "message": f"Package '{pkg.package_name}' deprecated.",
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/packages/{package_id}/reviews",
    summary="Submit Rating & Review",
    description="Submits a 1-5 star user rating and review text for an agent package.",
)
async def add_review(
    package_id: uuid.UUID,
    rating: int = Body(..., ge=1, le=5),
    review_text: str = Body(..., min_length=3),
    sec_ctx: SecurityContext = Depends(get_current_security_context),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    service = MarketplaceExperienceService(db)
    try:
        rev = await service.add_review(sec_ctx, package_id, rating, review_text)
        return {
            "review_id": str(rev.id),
            "package_id": str(rev.package_id),
            "rating": rev.rating,
            "review_text": rev.review_text,
            "package_version": rev.package_version,
            "created_at": rev.created_at.isoformat(),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get(
    "/packages/{package_id}/reviews",
    summary="Get Package Reviews & Rating Summary",
    description="Fetches user reviews and average rating score for a package.",
)
async def get_reviews(
    package_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    service = MarketplaceExperienceService(db)
    reviews = await service.repo.list_reviews(package_id)
    summary = await service.repo.get_rating_summary(package_id)
    return {
        "summary": summary,
        "reviews": [
            {
                "id": str(r.id),
                "rating": r.rating,
                "review_text": r.review_text,
                "package_version": r.package_version,
                "created_at": r.created_at.isoformat(),
            }
            for r in reviews
        ],
    }


@router.get(
    "/analytics",
    summary="Marketplace Health Analytics Dashboard",
    description="Exposes operational marketplace KPIs (downloads, active installs, upgrade rate, ratings).",
)
async def get_analytics(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    service = MarketplaceExperienceService(db)
    return await service.repo.get_analytics_dashboard()


@router.get(
    "/publishers/{publisher_name}",
    summary="Get Verified Publisher Profile",
    description="Fetches verified developer/publisher profile and trust badge credentials.",
)
async def get_publisher_profile(
    publisher_name: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    service = MarketplaceExperienceService(db)
    return await service.get_publisher_profile(publisher_name)
