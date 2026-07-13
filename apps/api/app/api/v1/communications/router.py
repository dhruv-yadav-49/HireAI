import uuid
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_request_context
from app.core.context import RequestContext
from app.core.exceptions import ValidationException
from app.db.session import get_db
from app.models.enums import CommunicationStatus, DeliveryEvent, ProviderType, CommunicationChannel
from app.models.communication import Communication
from app.models.communication_template import CommunicationTemplate
from app.models.communication_provider import CommunicationProvider
from app.models.communication_delivery import CommunicationDelivery
from app.schemas.communication import (
    CommunicationTemplateCreateRequest,
    CommunicationTemplateUpdateRequest,
    CommunicationTemplateResponse,
    CommunicationTemplateListResponse,
    CommunicationProviderCreateRequest,
    CommunicationProviderUpdateRequest,
    CommunicationProviderResponse,
    CommunicationProviderListResponse,
    CommunicationSendRequest,
    CommunicationResponse,
    CommunicationListResponse,
    CommunicationDeliveryResponse,
    CommunicationDeliveryListResponse,
)
from app.services.communication_service import CommunicationService
from app.services.communication_dispatcher import CommunicationDispatcher
from app.services.provider_registry import ProviderRegistry
from app.services.template_engine import TemplateEngine

router = APIRouter(prefix="/communications", tags=["communications"])


# ── 1. Templates Management Endpoints ──────────────────────────────────────────

@router.post("/templates", response_model=CommunicationTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    req: CommunicationTemplateCreateRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db)
):
    """Creates a communication template for an organization."""
    # 1. Enforce channel validation rules
    TemplateEngine.validate_template_rules(req.channel.value, req.subject_template, req.body_template)

    # 2. Variable validation registry creation (parse and record placeholders)
    extracted_vars = TemplateEngine.extract_variables(req.body_template)
    if req.subject_template:
        extracted_vars = list(set(extracted_vars + TemplateEngine.extract_variables(req.subject_template)))

    # Save template
    template = CommunicationTemplate(
        organization_id=ctx.tenant_id,
        name=req.name,
        channel=req.channel,
        subject_template=req.subject_template,
        body_template=req.body_template,
        variables_json=extracted_vars,
        enabled=req.enabled if req.enabled is not None else True,
        created_by=ctx.user.id,
        updated_by=ctx.user.id,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


@router.get("/templates", response_model=CommunicationTemplateListResponse)
async def list_templates(
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db)
):
    """Lists active templates for the tenant organization."""
    stmt = select(CommunicationTemplate).where(
        CommunicationTemplate.organization_id == ctx.tenant_id,
        CommunicationTemplate.deleted_at.is_(None)
    )
    res = await db.execute(stmt)
    items = res.scalars().all()
    return CommunicationTemplateListResponse(items=items, total=len(items))


@router.patch("/templates/{id}", response_model=CommunicationTemplateResponse)
async def update_template(
    id: uuid.UUID,
    req: CommunicationTemplateUpdateRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db)
):
    """Updates an existing template configuration and increments its version snapshot."""
    stmt = select(CommunicationTemplate).where(
        CommunicationTemplate.id == id,
        CommunicationTemplate.organization_id == ctx.tenant_id,
        CommunicationTemplate.deleted_at.is_(None)
    )
    res = await db.execute(stmt)
    template = res.scalar()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found.")

    if req.name is not None:
        template.name = req.name
    if req.subject_template is not None:
        template.subject_template = req.subject_template
    if req.body_template is not None:
        template.body_template = req.body_template
    if req.enabled is not None:
        template.enabled = req.enabled

    # Perform validation checks if modified
    TemplateEngine.validate_template_rules(template.channel.value, template.subject_template, template.body_template)

    # Re-extract variables
    extracted_vars = TemplateEngine.extract_variables(template.body_template)
    if template.subject_template:
        extracted_vars = list(set(extracted_vars + TemplateEngine.extract_variables(template.subject_template)))
    template.variables_json = extracted_vars

    # Increment version
    template.version += 1
    template.updated_by = ctx.user.id

    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


@router.delete("/templates/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db)
):
    """Soft deletes a template configuration."""
    stmt = select(CommunicationTemplate).where(
        CommunicationTemplate.id == id,
        CommunicationTemplate.organization_id == ctx.tenant_id,
        CommunicationTemplate.deleted_at.is_(None)
    )
    res = await db.execute(stmt)
    template = res.scalar()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found.")

    template.deleted_at = datetime.now(timezone.utc)
    db.add(template)
    await db.commit()


# ── 2. Providers Management Endpoints ──────────────────────────────────────────

@router.post("/providers", response_model=CommunicationProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_provider(
    req: CommunicationProviderCreateRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db)
):
    """Configures a communication provider setup for the tenant organization."""
    # 1. Structural credentials validation check
    provider_client = ProviderRegistry.get_provider(req.provider_type, req.channel.value)
    await provider_client.validate(req.configuration_json, req.credentials_json)

    # If is_default, unset other default provider for this channel
    if req.is_default:
        await db.execute(
            update(CommunicationProvider)
            .where(
                CommunicationProvider.organization_id == ctx.tenant_id,
                CommunicationProvider.channel == req.channel,
                CommunicationProvider.is_default == True
            )
            .values(is_default=False)
        )

    provider = CommunicationProvider(
        organization_id=ctx.tenant_id,
        provider_type=req.provider_type,
        channel=req.channel,
        display_name=req.display_name,
        credentials_json=req.credentials_json,
        configuration_json=req.configuration_json,
        capabilities_json=req.capabilities_json,
        is_default=req.is_default,
        enabled=req.enabled if req.enabled is not None else True,
        health_status="UNKNOWN"
    )
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return provider


@router.get("/providers", response_model=CommunicationProviderListResponse)
async def list_providers(
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db)
):
    """Lists configured providers for the organization."""
    stmt = select(CommunicationProvider).where(
        CommunicationProvider.organization_id == ctx.tenant_id
    )
    res = await db.execute(stmt)
    items = res.scalars().all()
    return CommunicationProviderListResponse(items=items, total=len(items))


@router.patch("/providers/{id}", response_model=CommunicationProviderResponse)
async def update_provider(
    id: uuid.UUID,
    req: CommunicationProviderUpdateRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db)
):
    """Updates provider details, credential parameters, or configuration JSON settings."""
    stmt = select(CommunicationProvider).where(
        CommunicationProvider.id == id,
        CommunicationProvider.organization_id == ctx.tenant_id
    )
    res = await db.execute(stmt)
    provider = res.scalar()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider configuration not found.")

    if req.display_name is not None:
        provider.display_name = req.display_name
    if req.credentials_json is not None:
        provider.credentials_json = req.credentials_json
    if req.configuration_json is not None:
        provider.configuration_json = req.configuration_json
    if req.capabilities_json is not None:
        provider.capabilities_json = req.capabilities_json
    if req.enabled is not None:
        provider.enabled = req.enabled
    if req.is_default is not None:
        provider.is_default = req.is_default

    # Run structural validations
    provider_client = ProviderRegistry.get_provider(provider.provider_type, provider.channel.value)
    await provider_client.validate(provider.configuration_json, provider.credentials_json)

    if req.is_default:
        await db.execute(
            update(CommunicationProvider)
            .where(
                CommunicationProvider.organization_id == ctx.tenant_id,
                CommunicationProvider.channel == provider.channel,
                CommunicationProvider.is_default == True,
                CommunicationProvider.id != provider.id
            )
            .values(is_default=False)
        )

    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return provider


@router.post("/providers/{id}/test")
async def test_provider_health(
    id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db)
):
    """Executes a diagnostic health connection check to the external provider API."""
    stmt = select(CommunicationProvider).where(
        CommunicationProvider.id == id,
        CommunicationProvider.organization_id == ctx.tenant_id
    )
    res = await db.execute(stmt)
    provider = res.scalar()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found.")

    provider_client = ProviderRegistry.get_provider(provider.provider_type, provider.channel.value)
    healthy = await provider_client.health_check(provider.configuration_json, provider.credentials_json)
    
    # Save status
    provider.health_status = "HEALTHY" if healthy else "UNHEALTHY"
    db.add(provider)
    await db.commit()

    return {"id": str(provider.id), "health_status": provider.health_status, "healthy": healthy}


# ── 3. Communications Dispatch & History Endpoints ─────────────────────────────

@router.post("/send", response_model=CommunicationResponse, status_code=status.HTTP_201_CREATED)
async def send_communication(
    req: CommunicationSendRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db)
):
    """Enqueues a new outbound communication (email, whatsapp, sms) and processes dynamic context."""
    comms_service = CommunicationService(db)
    
    # Check if a custom idempotency key is supplied, else fallback
    # For user manual api sends, auto-deduping by timestamp/recipient works nicely
    idemp_key = f"manual_{ctx.request_id}_{req.recipient}_{int(datetime.now(timezone.utc).timestamp())}"
    
    com = await comms_service.queue_communication(ctx, req, idempotency_key=idemp_key)
    return com


@router.get("", response_model=CommunicationListResponse)
async def list_communications(
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db)
):
    """Lists history log of all outgoing and inbound communications."""
    stmt = select(Communication).where(
        Communication.organization_id == ctx.tenant_id
    ).order_by(Communication.created_at.desc())
    
    res = await db.execute(stmt)
    items = res.scalars().all()
    return CommunicationListResponse(items=items, total=len(items))


@router.get("/{id}", response_model=CommunicationResponse)
async def get_communication(
    id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves full details of a specific communication record."""
    stmt = select(Communication).where(
        Communication.id == id,
        Communication.organization_id == ctx.tenant_id
    )
    res = await db.execute(stmt)
    com = res.scalar()
    if not com:
        raise HTTPException(status_code=404, detail="Communication log not found.")
    return com


@router.get("/{id}/delivery", response_model=CommunicationDeliveryListResponse)
async def get_delivery_timeline(
    id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db)
):
    """Lists chronological audit events logs for a specific communication dispatch."""
    # Ensure ownership/tenant isolation
    stmt_com = select(Communication.id).where(
        Communication.id == id,
        Communication.organization_id == ctx.tenant_id
    )
    res_com = await db.execute(stmt_com)
    if not res_com.scalar():
        raise HTTPException(status_code=404, detail="Communication not found.")

    stmt = select(CommunicationDelivery).where(
        CommunicationDelivery.communication_id == id
    ).order_by(CommunicationDelivery.sequence_no.asc())
    
    res = await db.execute(stmt)
    items = res.scalars().all()
    return CommunicationDeliveryListResponse(items=items, total=len(items))


# ── 4. Future Reserved Placeholders Stubs (Not Implemented) ──────────────────────

@router.post("/templates/{id}/preview")
async def preview_template(id: uuid.UUID):
    """Reserved Endpoint Preview Stub."""
    return {"message": "Reserved preview endpoint placeholder", "status": "NotImplemented"}


@router.post("/templates/import")
async def import_templates():
    """Reserved Endpoint Import Stub."""
    return {"message": "Reserved template import endpoint placeholder", "status": "NotImplemented"}


@router.post("/providers/{id}/disable")
async def disable_provider(id: uuid.UUID):
    """Reserved Endpoint Disable Stub."""
    return {"message": "Reserved provider disable endpoint placeholder", "status": "NotImplemented"}


@router.post("/providers/{id}/enable")
async def enable_provider(id: uuid.UUID):
    """Reserved Endpoint Enable Stub."""
    return {"message": "Reserved provider enable endpoint placeholder", "status": "NotImplemented"}


@router.post("/providers/{id}/validate-credentials")
async def validate_credentials(id: uuid.UUID):
    """Reserved Endpoint Credentials Validation Stub."""
    return {"message": "Reserved credentials validation endpoint placeholder", "status": "NotImplemented"}


@router.post("/{id}/retry")
async def retry_communication(id: uuid.UUID):
    """Reserved Endpoint Manual Retry Stub."""
    return {"message": "Reserved manual retry endpoint placeholder", "status": "NotImplemented"}


@router.post("/{id}/cancel")
async def cancel_communication(id: uuid.UUID):
    """Reserved Endpoint Cancel Stub."""
    return {"message": "Reserved cancel endpoint placeholder", "status": "NotImplemented"}


@router.post("/bulk")
async def send_bulk_communication():
    """Reserved Endpoint Bulk Dispatch Stub."""
    return {"message": "Reserved bulk dispatch endpoint placeholder", "status": "NotImplemented"}


@router.get("/conversations/{id}")
async def get_conversation_history(id: uuid.UUID):
    """Reserved Endpoint Conversation History Stub."""
    return {"message": "Reserved conversation history timeline endpoint placeholder", "status": "NotImplemented"}


@router.get("/leads/{id}/communications")
async def get_lead_communication_logs(id: uuid.UUID):
    """Reserved Endpoint Lead Communication logs Timeline Stub."""
    return {"message": "Reserved lead communications timeline logs endpoint placeholder", "status": "NotImplemented"}
