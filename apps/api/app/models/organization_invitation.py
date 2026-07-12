import uuid
from datetime import datetime

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.models.enums import InvitationStatus, OrganizationRole


class OrganizationInvitation(Base, TimestampMixin):
    """Schema only in Sprint 2A -- no repository, no service, no routes yet.
    Full field set is built now so the migration doesn't need to change
    again when Sprint 2B adds the invite/accept logic, NotificationService,
    and token generation.

    Following ADR-018: this table never generates a JWT. token_hash stores
    SHA-256(raw_token) the same way UserSession does -- the raw token is
    only ever emailed, never persisted.
    """

    __tablename__ = "organization_invitations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[OrganizationRole] = mapped_column(
        SAEnum(OrganizationRole, name="organization_role", native_enum=False), nullable=False
    )

    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # sha256 hex digest
    status: Mapped[InvitationStatus] = mapped_column(
        SAEnum(InvitationStatus, name="invitation_status", native_enum=False),
        default=InvitationStatus.PENDING,
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    __table_args__ = (
        Index("ix_org_invitations_email", "email"),
        Index("ix_org_invitations_token_hash", "token_hash"),
        Index("ix_org_invitations_status", "status"),
        # Prevents two concurrent invite requests from both succeeding for
        # the same org+email -- enforced at the DB level so it holds even
        # under a race, not just when the service checks first. Uses the
        # raw string value ("PENDING") since this is a plain-string check
        # constraint at the SQL level, not a Python enum comparison.
        Index(
            "uq_org_invitations_pending_email",
            "organization_id",
            "email",
            unique=True,
            postgresql_where=(status == "PENDING"),
        ),
    )
