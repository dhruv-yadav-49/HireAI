"""
app/models/playground_session.py

PlaygroundSession model tracking active playground DX sessions.

CTO Refinement #11: Life-cycle states ACTIVE -> IDLE -> EXPIRED -> ARCHIVED.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

from app.db.base import Base
from app.models.enums import PlaygroundSessionStatus, SandboxIsolationLevel


class PlaygroundSession(Base):
    """Active developer playground session with isolation level and TTL."""

    __tablename__ = "playground_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False, default="Playground Session")

    status: Mapped[PlaygroundSessionStatus] = mapped_column(
        SQLEnum(
            PlaygroundSessionStatus,
            name="playground_session_status",
            native_enum=False,
            create_constraint=False,
        ),
        nullable=False,
        default=PlaygroundSessionStatus.ACTIVE,
    )

    isolation_level: Mapped[SandboxIsolationLevel] = mapped_column(
        SQLEnum(
            SandboxIsolationLevel,
            name="sandbox_isolation_level",
            native_enum=False,
            create_constraint=False,
        ),
        nullable=False,
        default=SandboxIsolationLevel.READ_ONLY,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
