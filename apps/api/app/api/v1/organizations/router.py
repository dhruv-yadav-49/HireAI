"""
app/api/v1/organizations/router.py

Organization endpoints (Sprint 2C):
  GET  /organizations/current   — active org for this session
  POST /organizations/switch    — switch active org for this session
  GET  /organizations/settings  — org settings (idempotent create on first access)
  PATCH /organizations/settings — update settings (OWNER/ADMIN only)
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_request_context, get_current_user, get_current_session
from app.core.context import RequestContext
from app.db.session import get_db
from app.models.user import User
from app.models.user_session import UserSession
from app.schemas.organization import (
    OrganizationMeResponse,
    OrganizationSettingsResponse,
    OrganizationSettingsUpdateRequest,
    OrganizationSwitchRequest,
    OrganizationCreateRequest,
    OrganizationResponse,
)
from app.services.organization_service import OrganizationService

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=201,
    summary="Create organization",
    description="Creates a new organization and registers the caller as the OWNER. Sets the organization as active for the current session.",
)
async def create_organization(
    data: OrganizationCreateRequest,
    current_user: User = Depends(get_current_user),
    session: UserSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    service = OrganizationService(db)
    return await service.create_organization(current_user, data, session=session)


@router.get(
    "/current",
    response_model=OrganizationMeResponse,
    summary="Get active organization",
    description=(
        "Returns the organization currently active in this session, along with "
        "the caller's role. Returns 404 if no organization is set — the client "
        "should redirect to the organization selector."
    ),
)
async def get_current_organization(
    ctx: RequestContext = Depends(get_request_context),
) -> OrganizationMeResponse:
    return OrganizationMeResponse(
        id=ctx.organization.id,
        name=ctx.organization.name,
        slug=ctx.organization.slug,
        industry=ctx.organization.industry,
        company_size=ctx.organization.company_size,
        country=ctx.organization.country,
        timezone=ctx.organization.timezone,
        logo_url=ctx.organization.logo_url,
        status=ctx.organization.status,
        role=ctx.role,
    )


@router.post(
    "/switch",
    response_model=OrganizationMeResponse,
    summary="Switch active organization",
    description=(
        "Switches this session's active organization. Only the session (device) "
        "is affected — other active sessions remain unchanged. "
        "The user must have an ACTIVE membership in the target organization."
    ),
)
async def switch_organization(
    data: OrganizationSwitchRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> OrganizationMeResponse:
    service = OrganizationService(db)
    return await service.switch_organization(ctx, data)


@router.get(
    "/settings",
    response_model=OrganizationSettingsResponse,
    summary="Get organization settings",
    description=(
        "Returns the active organization's settings. Creates a default row on "
        "first access (idempotent). Any active member can read settings."
    ),
)
async def get_organization_settings(
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> OrganizationSettingsResponse:
    service = OrganizationService(db)
    settings_row = await service.get_or_create_settings(ctx)
    return OrganizationSettingsResponse(
        organization_id=settings_row.organization_id,
        timezone=settings_row.timezone,
        currency=settings_row.currency,
        language=settings_row.language,
        business_hours=settings_row.business_hours,
        email_signature=settings_row.email_signature,
    )


@router.patch(
    "/settings",
    response_model=OrganizationSettingsResponse,
    summary="Update organization settings",
    description=(
        "Updates the active organization's settings. All fields are optional "
        "(PATCH semantics). business_hours uses day-level merge — provide a "
        "complete day object for each day you want to update. "
        "Requires OWNER or ADMIN role."
    ),
)
async def update_organization_settings(
    data: OrganizationSettingsUpdateRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> OrganizationSettingsResponse:
    service = OrganizationService(db)
    settings_row = await service.update_settings(ctx, data)
    return OrganizationSettingsResponse(
        organization_id=settings_row.organization_id,
        timezone=settings_row.timezone,
        currency=settings_row.currency,
        language=settings_row.language,
        business_hours=settings_row.business_hours,
        email_signature=settings_row.email_signature,
    )
