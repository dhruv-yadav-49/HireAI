"""
app/models/agent_package_version.py

Database model for immutable package release history and channels.
CTO Refinements #4, #10:
  - Immutable release history
  - Release channels: STABLE, BETA, NIGHTLY, DEPRECATED
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import ReleaseChannel


class AgentPackageVersion(Base):
    """Tracks immutable release version history for published agent packages."""

    __tablename__ = "agent_package_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_packages.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    channel: Mapped[ReleaseChannel] = mapped_column(
        SQLEnum(ReleaseChannel, name="release_channel", native_enum=False),
        default=ReleaseChannel.STABLE,
        nullable=False,
    )
    manifest_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    changelog: Mapped[str] = mapped_column(Text, nullable=False, default="Initial release")

    released_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
