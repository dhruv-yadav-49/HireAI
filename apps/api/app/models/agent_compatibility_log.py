"""
app/models/agent_compatibility_log.py

Database model for agent compatibility audit logs and dependency failure records.
CTO Refinements #4, #10:
  - Logs tool, model, SDK version, and permission compatibility checks
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentCompatibilityLog(Base):
    """Audit logs for marketplace dependency resolution and compatibility checks."""

    __tablename__ = "agent_compatibility_logs"

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
    compatible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    check_type: Mapped[str] = mapped_column(String(50), nullable=False)  # MODEL, TOOL, SDK, PERMISSION, DEPENDENCY
    details_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
