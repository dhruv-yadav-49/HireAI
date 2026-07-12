import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator, EmailStr

from app.models.enums import LeadPriority, LeadSource, LeadStatus, CreatedSource, ActorType, LeadActivityType
from app.schemas.organization import VALID_CURRENCIES

_COLOR_RE = re.compile(r"^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$")


# ── Tag Schemas ─────────────────────────────────────────────────────────────

class LeadTagCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    color: str = Field(default="#808080")

    @field_validator("color")
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        if not _COLOR_RE.match(v):
            raise ValueError("Color must be a valid 3- or 6-character hex string (e.g., '#FFF' or '#808080')")
        return v


class LeadTagResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    color: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Note Schemas ────────────────────────────────────────────────────────────

class LeadNoteCreateRequest(BaseModel):
    content: str = Field(min_length=1)


class LeadNoteResponse(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    author_id: uuid.UUID
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Lead Schemas ────────────────────────────────────────────────────────────

class LeadCreateRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=255)
    last_name: str = Field(min_length=1, max_length=255)
    company_name: str = Field(min_length=1, max_length=255)
    job_title: str = Field(min_length=1, max_length=255)
    
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, min_length=5, max_length=45)
    website: Optional[str] = Field(default=None, max_length=255)
    country: Optional[str] = Field(default=None, max_length=100)
    city: Optional[str] = Field(default=None, max_length=100)
    
    source: LeadSource = LeadSource.MANUAL
    created_source: CreatedSource = CreatedSource.MANUAL_UI
    status: LeadStatus = LeadStatus.NEW
    priority: LeadPriority = LeadPriority.LOW
    
    estimated_value: Decimal = Field(default=Decimal("0.00"), ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    
    is_starred: bool = False
    
    assigned_to: Optional[uuid.UUID] = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        if v.upper() not in VALID_CURRENCIES:
            raise ValueError(f"Invalid ISO 4217 currency: {v}")
        return v.upper()

    @model_validator(mode="after")
    def validate_contact_methods(self) -> "LeadCreateRequest":
        if not self.email and not self.phone:
            raise ValueError("At least one contact method (email or phone) must be provided.")
        return self


class LeadUpdateRequest(BaseModel):
    """Update schema. Enforces optimistic lock version parameter."""
    version: int = Field(..., description="Current lead version for optimistic locking")
    
    first_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    last_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    company_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    job_title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, min_length=5, max_length=45)
    website: Optional[str] = Field(default=None, max_length=255)
    country: Optional[str] = Field(default=None, max_length=100)
    city: Optional[str] = Field(default=None, max_length=100)
    
    source: Optional[LeadSource] = None
    status: Optional[LeadStatus] = None
    priority: Optional[LeadPriority] = None
    
    estimated_value: Optional[Decimal] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    
    is_starred: Optional[bool] = None
    assigned_to: Optional[uuid.UUID] = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str | None) -> str | None:
        if v is not None:
            if v.upper() not in VALID_CURRENCIES:
                raise ValueError(f"Invalid ISO 4217 currency: {v}")
            return v.upper()
        return v

    @model_validator(mode="after")
    def validate_contact_methods(self) -> "LeadUpdateRequest":
        # Only validate when email or phone is updated.
        # If both are sent as None/null explicitly, it would violate the rule.
        # We check values present in model_fields_set.
        fields = self.model_fields_set
        if "email" in fields or "phone" in fields:
            # If one is present and non-null, it's valid.
            # If both are explicitly provided as None/null, fail validation.
            email_val = getattr(self, "email")
            phone_val = getattr(self, "phone")
            if email_val is None and phone_val is None:
                raise ValueError("At least one contact method (email or phone) must be provided.")
        return self


class LeadResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    lead_number: int
    created_by: uuid.UUID
    updated_by: uuid.UUID
    assigned_to: Optional[uuid.UUID] = None

    first_name: str
    last_name: str
    company_name: str
    job_title: str

    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None

    source: LeadSource
    created_source: CreatedSource
    status: LeadStatus
    priority: LeadPriority

    estimated_value: Decimal
    currency: str
    is_starred: bool
    version: int

    last_contacted_at: Optional[datetime] = None
    next_followup_at: Optional[datetime] = None
    last_activity_at: datetime

    created_at: datetime
    updated_at: datetime

    tags: list[LeadTagResponse] = []

    model_config = {"from_attributes": True}


class LeadListResponse(BaseModel):
    items: list[LeadResponse]
    total: int
    page: int
    page_size: int


# ── Activity Schemas ─────────────────────────────────────────────────────────

class LeadActivityResponse(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    actor_id: Optional[uuid.UUID] = None
    actor_type: ActorType
    activity_type: LeadActivityType
    metadata: dict[str, Any] = Field(validation_alias="event_metadata")
    metadata_version: int
    created_at: datetime

    model_config = {"from_attributes": True}
