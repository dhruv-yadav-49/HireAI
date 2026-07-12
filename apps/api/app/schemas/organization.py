"""
app/schemas/organization.py

Pydantic schemas for organization endpoints.
All validators are strict — they raise 422 with clear messages.
"""

import re
import uuid
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import OrganizationRole, OrganizationStatus

# ── Validation constants ───────────────────────────────────────────────────────

# ISO 4217 most-used currency codes
VALID_CURRENCIES = frozenset({
    "USD", "EUR", "GBP", "INR", "AED", "SGD", "AUD", "CAD", "JPY",
    "CNY", "CHF", "SEK", "NOK", "DKK", "NZD", "HKD", "MXN", "BRL",
    "ZAR", "KRW", "IDR", "MYR", "PHP", "THB", "VND", "TRY", "SAR",
})

# ISO 639-1 language codes
VALID_LANGUAGES = frozenset({
    "en", "hi", "fr", "de", "es", "ar", "zh", "ja", "pt", "ru",
    "ko", "it", "nl", "pl", "tr", "vi", "th", "id", "ms", "sv",
    "da", "fi", "nb", "cs", "sk", "hu", "ro", "bg", "hr", "uk",
})

VALID_DAYS = frozenset({
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
})

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")  # strict HH:MM


# ── Organization basic CRUD ────────────────────────────────────────────────────

class OrganizationCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    industry: str | None = None
    company_size: str | None = None
    country: str | None = None
    timezone: str | None = None


class OrganizationUpdateRequest(BaseModel):
    """All fields optional — PATCH semantics, only provided fields change."""
    name: str | None = Field(default=None, min_length=2, max_length=255)
    industry: str | None = None
    company_size: str | None = None
    country: str | None = None
    timezone: str | None = None
    logo_url: str | None = None


class OrganizationResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    industry: str | None
    company_size: str | None
    country: str | None
    timezone: str | None
    logo_url: str | None
    status: OrganizationStatus

    model_config = {"from_attributes": True}


class OrganizationMeResponse(OrganizationResponse):
    """Same as OrganizationResponse, plus the caller's role in this org."""
    role: OrganizationRole


# ── Organization Switch ────────────────────────────────────────────────────────

class OrganizationSwitchRequest(BaseModel):
    organization_id: uuid.UUID


# ── Organization Settings ──────────────────────────────────────────────────────

class DaySchedule(BaseModel):
    """Schedule for one day of the week.

    Day-level merge semantics: when a client sends a day object in PATCH,
    the ENTIRE day object is replaced (not field-by-field). Clients must
    always send a complete day object when updating a specific day.
    """
    enabled: bool
    start: Optional[str] = None  # "HH:MM"
    end: Optional[str] = None    # "HH:MM"

    @field_validator("start", "end")
    @classmethod
    def validate_time_format(cls, v: str | None) -> str | None:
        if v is not None and not _TIME_RE.match(v):
            raise ValueError("Time must be in HH:MM format (e.g., '09:00')")
        return v

    @model_validator(mode="after")
    def require_times_when_enabled(self) -> "DaySchedule":
        if self.enabled and (not self.start or not self.end):
            raise ValueError("start and end are required when enabled=True")
        return self


class OrganizationSettingsResponse(BaseModel):
    organization_id: uuid.UUID
    timezone: str
    currency: str
    language: str
    business_hours: Optional[dict] = None  # raw JSONB, validated on write
    email_signature: Optional[str] = None

    model_config = {"from_attributes": True}


class OrganizationSettingsUpdateRequest(BaseModel):
    """All fields optional — PATCH semantics.
    business_hours uses day-level merge (see DaySchedule docstring).
    """

    timezone: Optional[str] = None
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    language: Optional[str] = Field(default=None, min_length=2, max_length=5)
    business_hours: Optional[dict[str, DaySchedule]] = None
    email_signature: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str | None) -> str | None:
        if v is not None:
            try:
                ZoneInfo(v)
            except (ZoneInfoNotFoundError, KeyError):
                raise ValueError(
                    f"Invalid IANA timezone: '{v}'. "
                    "Use a valid name such as 'Asia/Kolkata', 'UTC', or 'Europe/London'."
                )
        return v

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str | None) -> str | None:
        if v and v.upper() not in VALID_CURRENCIES:
            raise ValueError(
                f"'{v}' is not a supported ISO 4217 currency code. "
                f"Supported: {', '.join(sorted(VALID_CURRENCIES))}"
            )
        return v.upper() if v else v

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str | None) -> str | None:
        if v and v.lower() not in VALID_LANGUAGES:
            raise ValueError(
                f"'{v}' is not a supported ISO 639-1 language code. "
                f"Supported: {', '.join(sorted(VALID_LANGUAGES))}"
            )
        return v.lower() if v else v

    @field_validator("business_hours")
    @classmethod
    def validate_day_keys(
        cls, v: dict[str, DaySchedule] | None
    ) -> dict[str, DaySchedule] | None:
        if v:
            invalid = set(v.keys()) - VALID_DAYS
            if invalid:
                raise ValueError(
                    f"Invalid day key(s): {invalid}. "
                    f"Valid keys: {', '.join(sorted(VALID_DAYS))}"
                )
        return v
