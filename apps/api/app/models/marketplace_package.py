"""
app/models/marketplace_package.py

Database model for published marketplace agent packages (.hireagent artifacts).
CTO Refinements #1-#6:
  - Manifest versioning (manifest_version, api_version, sdk_version)
  - Signature fields (package_hash, signature, publisher_id, certificate_id)
  - Registry version tracking (latest_version, stable_version, beta_version)
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SQLEnum, String, Text, func, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AgentLifecycleStatus, AgentPackageType


class MarketplacePackage(Base):
    """Stores uploaded and published marketplace agent packages."""

    __tablename__ = "marketplace_packages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    package_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(String(100), nullable=False)
    package_type: Mapped[AgentPackageType] = mapped_column(
        SQLEnum(AgentPackageType, name="agent_package_type", native_enum=False),
        default=AgentPackageType.COMMUNITY,
        nullable=False,
    )

    # Versioning (CTO #1, #6)
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    manifest_version: Mapped[int] = mapped_column(default=1, nullable=False)
    api_version: Mapped[str] = mapped_column(String(50), default="1.0", nullable=False)
    sdk_version: Mapped[str] = mapped_column(String(50), default=">=1.0", nullable=False)
    runtime_requirement: Mapped[str] = mapped_column(String(50), default=">=1.0", nullable=False)

    stable_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    beta_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    latest_version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)

    # Manifest payload & security signature (CTO #2, #3)
    manifest_yaml: Mapped[str] = mapped_column(Text, nullable=False)
    manifest_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    package_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256
    signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Reserved for cert sig
    publisher_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    certificate_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Lifecycle state machine (CTO #5)
    lifecycle_status: Mapped[AgentLifecycleStatus] = mapped_column(
        SQLEnum(AgentLifecycleStatus, name="agent_lifecycle_status", native_enum=False),
        default=AgentLifecycleStatus.DRAFT,
        nullable=False,
    )
    validation_results_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
