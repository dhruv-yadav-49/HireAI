import uuid
import zoneinfo
from datetime import datetime
from typing import Any, Optional

try:
    from croniter import croniter
except ImportError:
    class DummyCroniter:
        @staticmethod
        def is_valid(expr: str) -> bool:
            return len(expr.split()) >= 5
    croniter = DummyCroniter
from pydantic import BaseModel, Field, field_validator

from app.models.enums import JobExecutionStatus, JobStatus, JobType


class ScheduledJobCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    cron_expression: str = Field(..., min_length=5, max_length=100)
    job_type: JobType
    payload: Optional[dict[str, Any]] = None
    payload_version: Optional[int] = 1
    status: Optional[JobStatus] = JobStatus.ACTIVE
    timezone: Optional[str] = Field(None, max_length=100)
    max_retries: Optional[int] = Field(3, ge=0)

    @field_validator("cron_expression")
    @classmethod
    def validate_cron(cls, v: str) -> str:
        if not croniter.is_valid(v):
            raise ValueError(f"Invalid cron expression: {v}")
        return v

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            try:
                zoneinfo.ZoneInfo(v)
            except Exception:
                raise ValueError(f"Invalid IANA timezone name: {v}")
        return v


class ScheduledJobUpdateRequest(BaseModel):
    version: int = Field(..., description="Optimistic locking version field")
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    cron_expression: Optional[str] = Field(None, min_length=5, max_length=100)
    status: Optional[JobStatus] = None
    timezone: Optional[str] = Field(None, max_length=100)
    payload: Optional[dict[str, Any]] = None
    payload_version: Optional[int] = None
    max_retries: Optional[int] = Field(None, ge=0)

    @field_validator("cron_expression")
    @classmethod
    def validate_cron(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not croniter.is_valid(v):
                raise ValueError(f"Invalid cron expression: {v}")
        return v

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            try:
                zoneinfo.ZoneInfo(v)
            except Exception:
                raise ValueError(f"Invalid IANA timezone name: {v}")
        return v


class ScheduledJobResponse(BaseModel):
    id: uuid.UUID
    organization_id: Optional[uuid.UUID] = None
    name: str
    description: Optional[str] = None
    cron_expression: str
    job_type: JobType
    payload: dict[str, Any]
    payload_version: int
    status: JobStatus
    max_retries: int
    retry_count: int
    timezone: Optional[str] = None
    version: int
    last_run_at: Optional[datetime] = None
    next_run_at: datetime
    created_by: uuid.UUID
    updated_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobExecutionResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    organization_id: Optional[uuid.UUID] = None
    status: JobExecutionStatus
    execution_key: str
    attempt: int
    error_message: Optional[str] = None
    payload_snapshot: dict[str, Any]
    scheduler_instance: Optional[str] = None
    processed_records: int
    created_reminders: int
    published_events: int
    queued_notifications: int
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None

    model_config = {"from_attributes": True}


class ScheduledJobListResponse(BaseModel):
    items: list[ScheduledJobResponse]
    total: int
    page: int
    page_size: int


class JobExecutionListResponse(BaseModel):
    items: list[JobExecutionResponse]
    total: int
    page: int
    page_size: int
