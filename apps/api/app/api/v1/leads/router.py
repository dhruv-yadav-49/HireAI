"""
app/api/v1/leads/router.py

Protected Leads API Endpoints:
  GET   /leads             — Paginated, filtered list of leads
  POST  /leads             — Create a lead
  GET   /leads/{id}        — Get detailed lead details
  PATCH /leads/{id}        — Update lead details (version + transition rules)
  DELETE /leads/{id}       — Soft delete a lead

  POST  /leads/{id}/notes  — Append a note to a lead
  GET   /leads/{id}/notes  — Fetch notes for a lead

  POST  /leads/{id}/tags/{tag_id} — Assign a tag to a lead
  DELETE /leads/{id}/tags/{tag_id} — Unassign a tag from a lead

  GET   /leads/{id}/activities   — Get activity timeline

  POST  /leads/tags        — Create a tag within the organization

  Reserved endpoints:
    POST  /leads/{id}/restore
    POST  /leads/import
    GET   /leads/export
    PATCH /leads/bulk
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_request_context
from app.core.context import RequestContext
from app.db.session import get_db
from app.models.enums import LeadPriority, LeadSource, LeadStatus
from app.schemas.lead import (
    LeadActivityResponse,
    LeadCreateRequest,
    LeadListResponse,
    LeadNoteCreateRequest,
    LeadNoteResponse,
    LeadResponse,
    LeadTagCreateRequest,
    LeadTagResponse,
    LeadUpdateRequest,
)
from app.services.lead_service import LeadService

router = APIRouter(prefix="/leads", tags=["leads"])


# ── Tag Creation ──────────────────────────────────────────────────────────────

@router.post(
    "/tags",
    response_model=LeadTagResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create lead tag",
    description="Creates a normalized tag for lead categorization in the organization.",
)
async def create_tag(
    data: LeadTagCreateRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> LeadTagResponse:
    service = LeadService(db)
    tag = await service.create_tag(ctx, data)
    return LeadTagResponse.model_validate(tag)


# ── Lead CRUD ─────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=LeadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a lead",
    description="Creates a new lead. Generates a unique sequential lead number and assigns the lead.",
)
async def create_lead(
    data: LeadCreateRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> LeadResponse:
    service = LeadService(db)
    lead = await service.create_lead(ctx, data)
    
    # Resolve tags if any (initially empty)
    return LeadResponse(
        id=lead.id,
        organization_id=lead.organization_id,
        lead_number=lead.lead_number,
        created_by=lead.created_by,
        updated_by=lead.updated_by,
        assigned_to=lead.assigned_to,
        first_name=lead.first_name,
        last_name=lead.last_name,
        company_name=lead.company_name,
        job_title=lead.job_title,
        email=lead.email,
        phone=lead.phone,
        website=lead.website,
        country=lead.country,
        city=lead.city,
        source=lead.source,
        created_source=lead.created_source,
        status=lead.status,
        priority=lead.priority,
        estimated_value=lead.estimated_value,
        currency=lead.currency,
        is_starred=lead.is_starred,
        version=lead.version,
        last_contacted_at=lead.last_contacted_at,
        next_followup_at=lead.next_followup_at,
        last_activity_at=lead.last_activity_at,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
        tags=[],
    )


@router.get(
    "",
    response_model=LeadListResponse,
    summary="List leads",
    description="Lists active leads in the current tenant with sorting, filters, search, and pagination.",
)
async def list_leads(
    status: Optional[LeadStatus] = None,
    priority: Optional[LeadPriority] = None,
    assigned_to: Optional[uuid.UUID] = None,
    source: Optional[LeadSource] = None,
    search: Optional[str] = Query(None, description="Search by name, company, email, or phone"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at", description="Sort by created_at, estimated_value, last_name, or last_activity_at"),
    sort_dir: str = Query("desc", description="asc or desc"),
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> LeadListResponse:
    service = LeadService(db)
    items, total = await service.lead_repo.list(
        ctx=ctx,
        status=status.value if status else None,
        priority=priority.value if priority else None,
        assigned_to=assigned_to,
        source=source.value if source else None,
        search=search,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Convert to response objects
    lead_responses = []
    for lead in items:
        # Load tags via repo
        tags = await service.tag_repo.get_tags_for_lead(ctx, lead.id)
        lead_responses.append(
            LeadResponse(
                id=lead.id,
                organization_id=lead.organization_id,
                lead_number=lead.lead_number,
                created_by=lead.created_by,
                updated_by=lead.updated_by,
                assigned_to=lead.assigned_to,
                first_name=lead.first_name,
                last_name=lead.last_name,
                company_name=lead.company_name,
                job_title=lead.job_title,
                email=lead.email,
                phone=lead.phone,
                website=lead.website,
                country=lead.country,
                city=lead.city,
                source=lead.source,
                created_source=lead.created_source,
                status=lead.status,
                priority=lead.priority,
                estimated_value=lead.estimated_value,
                currency=lead.currency,
                is_starred=lead.is_starred,
                version=lead.version,
                last_contacted_at=lead.last_contacted_at,
                next_followup_at=lead.next_followup_at,
                last_activity_at=lead.last_activity_at,
                created_at=lead.created_at,
                updated_at=lead.updated_at,
                tags=[LeadTagResponse.model_validate(t) for t in tags],
            )
        )

    return LeadListResponse(
        items=lead_responses,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{id}",
    response_model=LeadResponse,
    summary="Get lead details",
    description="Fetches a lead's complete details. Returns 404 if not found or belongs to another tenant.",
)
async def get_lead(
    id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> LeadResponse:
    service = LeadService(db)
    lead = await service.lead_repo.get_by_id(ctx, id)
    if lead is None:
        from app.core.exceptions import LeadNotFoundException
        raise LeadNotFoundException()

    tags = await service.tag_repo.get_tags_for_lead(ctx, lead.id)
    return LeadResponse(
        id=lead.id,
        organization_id=lead.organization_id,
        lead_number=lead.lead_number,
        created_by=lead.created_by,
        updated_by=lead.updated_by,
        assigned_to=lead.assigned_to,
        first_name=lead.first_name,
        last_name=lead.last_name,
        company_name=lead.company_name,
        job_title=lead.job_title,
        email=lead.email,
        phone=lead.phone,
        website=lead.website,
        country=lead.country,
        city=lead.city,
        source=lead.source,
        created_source=lead.created_source,
        status=lead.status,
        priority=lead.priority,
        estimated_value=lead.estimated_value,
        currency=lead.currency,
        is_starred=lead.is_starred,
        version=lead.version,
        last_contacted_at=lead.last_contacted_at,
        next_followup_at=lead.next_followup_at,
        last_activity_at=lead.last_activity_at,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
        tags=[LeadTagResponse.model_validate(t) for t in tags],
    )


@router.patch(
    "/{id}",
    response_model=LeadResponse,
    summary="Update a lead",
    description="Updates a lead's details, enforcing optimistic locking version matches and state machine status transitions.",
)
async def update_lead(
    id: uuid.UUID,
    data: LeadUpdateRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> LeadResponse:
    service = LeadService(db)
    lead = await service.update_lead(ctx, id, data)

    tags = await service.tag_repo.get_tags_for_lead(ctx, lead.id)
    return LeadResponse(
        id=lead.id,
        organization_id=lead.organization_id,
        lead_number=lead.lead_number,
        created_by=lead.created_by,
        updated_by=lead.updated_by,
        assigned_to=lead.assigned_to,
        first_name=lead.first_name,
        last_name=lead.last_name,
        company_name=lead.company_name,
        job_title=lead.job_title,
        email=lead.email,
        phone=lead.phone,
        website=lead.website,
        country=lead.country,
        city=lead.city,
        source=lead.source,
        created_source=lead.created_source,
        status=lead.status,
        priority=lead.priority,
        estimated_value=lead.estimated_value,
        currency=lead.currency,
        is_starred=lead.is_starred,
        version=lead.version,
        last_contacted_at=lead.last_contacted_at,
        next_followup_at=lead.next_followup_at,
        last_activity_at=lead.last_activity_at,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
        tags=[LeadTagResponse.model_validate(t) for t in tags],
    )


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete a lead",
    description="Soft deletes the lead (sets deleted_at).",
)
async def delete_lead(
    id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = LeadService(db)
    await service.soft_delete_lead(ctx, id)


# ── Note Management ───────────────────────────────────────────────────────────

@router.post(
    "/{id}/notes",
    response_model=LeadNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add note",
    description="Appends a note to a lead, updating the lead's last activity timestamp.",
)
async def create_note(
    id: uuid.UUID,
    data: LeadNoteCreateRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> LeadNoteResponse:
    service = LeadService(db)
    note = await service.create_note(ctx, id, data)
    return LeadNoteResponse.model_validate(note)


@router.get(
    "/{id}/notes",
    response_model=list[LeadNoteResponse],
    summary="List notes",
    description="Retrieves all active notes for a lead.",
)
async def list_notes(
    id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> list[LeadNoteResponse]:
    service = LeadService(db)
    notes = await service.list_notes(ctx, id)
    return [LeadNoteResponse.model_validate(n) for n in notes]


# ── Tag Assignment ────────────────────────────────────────────────────────────

@router.post(
    "/{id}/tags/{tag_id}",
    summary="Assign tag",
    description="Assigns a tag to the lead.",
)
async def assign_tag(
    id: uuid.UUID,
    tag_id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    service = LeadService(db)
    await service.assign_tag_to_lead(ctx, id, tag_id)
    return {"success": True}


@router.delete(
    "/{id}/tags/{tag_id}",
    summary="Unassign tag",
    description="Removes a tag assignment from the lead.",
)
async def remove_tag(
    id: uuid.UUID,
    tag_id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    service = LeadService(db)
    await service.remove_tag_from_lead(ctx, id, tag_id)
    return {"success": True}


# ── Activity Timeline ─────────────────────────────────────────────────────────

@router.get(
    "/{id}/activities",
    response_model=list[LeadActivityResponse],
    summary="Get activities timeline",
    description="Fetches timeline activity logs for the lead, ordered newest first.",
)
async def list_activities(
    id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> list[LeadActivityResponse]:
    service = LeadService(db)
    activities = await service.list_activities(ctx, id)
    return [LeadActivityResponse.model_validate(a) for a in activities]


# ── Reserved Routes (Documentation & Placeholders) ────────────────────────────

@router.post(
    "/{id}/restore",
    response_model=LeadResponse,
    summary="Restore lead",
    description="Restores a previously soft-deleted lead.",
)
async def restore_lead(
    id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> LeadResponse:
    service = LeadService(db)
    lead = await service.restore_lead(ctx, id)
    tags = await service.tag_repo.get_tags_for_lead(ctx, lead.id)
    return LeadResponse(
        id=lead.id,
        organization_id=lead.organization_id,
        lead_number=lead.lead_number,
        created_by=lead.created_by,
        updated_by=lead.updated_by,
        assigned_to=lead.assigned_to,
        first_name=lead.first_name,
        last_name=lead.last_name,
        company_name=lead.company_name,
        job_title=lead.job_title,
        email=lead.email,
        phone=lead.phone,
        website=lead.website,
        country=lead.country,
        city=lead.city,
        source=lead.source,
        created_source=lead.created_source,
        status=lead.status,
        priority=lead.priority,
        estimated_value=lead.estimated_value,
        currency=lead.currency,
        is_starred=lead.is_starred,
        version=lead.version,
        last_contacted_at=lead.last_contacted_at,
        next_followup_at=lead.next_followup_at,
        last_activity_at=lead.last_activity_at,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
        tags=[LeadTagResponse.model_validate(t) for t in tags],
    )


@router.post(
    "/import",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    summary="Bulk import leads (Reserved)",
    description="Placeholder endpoint for CSV/API bulk lead ingestion.",
)
async def import_leads_placeholder():
    return {"detail": "Not implemented. Reserved for future Sprint."}


@router.get(
    "/export",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    summary="Export leads (Reserved)",
    description="Placeholder endpoint for tenant lead exports.",
)
async def export_leads_placeholder():
    return {"detail": "Not implemented. Reserved for future Sprint."}


@router.patch(
    "/bulk",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    summary="Bulk update leads (Reserved)",
    description="Placeholder endpoint for batch updates.",
)
async def bulk_update_placeholder():
    return {"detail": "Not implemented. Reserved for future Sprint."}
