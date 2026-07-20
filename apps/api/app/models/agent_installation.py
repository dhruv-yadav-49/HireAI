"""
app/models/agent_installation.py

Database model for tenant-scoped agent installations.
CTO Refinements #7, #8:
  - Verification stage before activation (INSTALLED -> VERIFIED -> ACTIVE)
  - Rollback support tracking current_version and previous_version
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, String, Text, func, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AgentInstallationStatus


class AgentInstallation(Base):
    """Tracks active tenant-scoped agent installations and their rollback versions."""

    __tablename__ = "agent_installations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_packages.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_key: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Versioning & Rollback support (CTO #8)
    current_version: Mapped[str] = mapped_column(String(50), nullable=False)
    previous_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    installed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Status (CTO #7: PENDING -> INSTALLED -> VERIFIED -> ACTIVE)
    status: Mapped[AgentInstallationStatus] = mapped_column(
        SQLEnum(AgentInstallationStatus, name="agent_installation_status", native_enum=False),
        default=AgentInstallationStatus.PENDING,
        nullable=False,
    )
    
    config_overrides_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    verification_results_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    installed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
