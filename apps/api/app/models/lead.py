import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, Numeric, String, BigInteger, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import BaseModel
from app.models.enums import LeadPriority, LeadSource, LeadStatus, CreatedSource


class Lead(BaseModel):
    """The canonical Lead business object.

    Tenancy is isolated strictly via organization_id. Unique constraints
    on email and phone are scoped per organization and non-deleted leads.
    """

    __tablename__ = "leads"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Sequential lead number unique per organization
    lead_number: Mapped[int] = mapped_column(BigInteger, nullable=False)

    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    updated_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )

    first_name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    job_title: Mapped[str] = mapped_column(String(255), nullable=False)

    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(45), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)

    source: Mapped[LeadSource] = mapped_column(
        SQLEnum(LeadSource, name="lead_source", native_enum=False),
        nullable=False,
        default=LeadSource.MANUAL,
    )
    created_source: Mapped[CreatedSource] = mapped_column(
        SQLEnum(CreatedSource, name="created_source", native_enum=False),
        nullable=False,
        default=CreatedSource.MANUAL_UI,
    )
    status: Mapped[LeadStatus] = mapped_column(
        SQLEnum(LeadStatus, name="lead_status", native_enum=False),
        nullable=False,
        default=LeadStatus.NEW,
    )
    priority: Mapped[LeadPriority] = mapped_column(
        SQLEnum(LeadPriority, name="lead_priority", native_enum=False),
        nullable=False,
        default=LeadPriority.LOW,
    )

    estimated_value: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False, default=0.00
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    is_starred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Optimistic Locking version attribute
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    last_contacted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_followup_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    notes = relationship("LeadNote", back_populates="lead", cascade="all, delete-orphan")
    activities = relationship("LeadActivity", back_populates="lead", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="lead", cascade="all, delete-orphan")
    tags = relationship(
        "LeadTag",
        secondary="lead_tag_assignments",
        back_populates="leads",
    )
