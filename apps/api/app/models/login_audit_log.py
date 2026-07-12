import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class LoginAuditLog(Base):
    """Audit log for authentication and session events.

    event_type values:
      Auth:    signup, login, logout, refresh, failed_login, account_locked
      Session: org_switch, session_revoke
    """

    __tablename__ = "login_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Optional: which session triggered this event (org_switch, session_revoke)
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Flexible event data for org_switch, future analytics.
    # Example: {"from_org_id": "uuid", "to_org_id": "uuid"}
    event_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
