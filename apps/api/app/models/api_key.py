import uuid
import hashlib
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, DateTime, Boolean, TEXT
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

from app.db.base import Base
from app.models.enums import APIKeyStatus


class APIKey(Base):
    """Scoped API key for programmatic platform access.

    ADR-021: Secret Abstraction — raw key is never stored, only SHA-256 hash.
    The prefix is stored in plaintext to enable efficient lookup.
    CTO refinement #3: created_from, last_ip, last_user_agent for incident response.
    """
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    hashed_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    prefix: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Scopes: list of strings e.g. ["jobs:read", "events:write"]
    scopes_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Lifecycle
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[APIKeyStatus] = mapped_column(
        SQLEnum(APIKeyStatus, name="api_key_status", native_enum=False, create_constraint=False),
        nullable=False,
        default=APIKeyStatus.ACTIVE,
    )

    # Incident response metadata (CTO refinement #3)
    created_from: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)   # e.g. "dashboard", "cli"
    last_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    last_user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
