import uuid
from datetime import datetime

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.models.enums import MemberStatus, OrganizationRole


class OrganizationMember(Base):
    __tablename__ = "organization_members"
    __table_args__ = (
        # A user can only have one membership row per organization.
        # Without this, a race condition (or a bug) could create
        # duplicate ACTIVE memberships for the same user+org.
        UniqueConstraint("organization_id", "user_id", name="uq_org_member_org_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    role: Mapped[OrganizationRole] = mapped_column(
        SAEnum(OrganizationRole, name="organization_role", native_enum=False), nullable=False
    )
    status: Mapped[MemberStatus] = mapped_column(
        SAEnum(MemberStatus, name="member_status", native_enum=False),
        default=MemberStatus.ACTIVE,
        nullable=False,
    )

    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    joined_at: Mapped[datetime] = mapped_column(server_default=func.now())

    organization: Mapped["Organization"] = relationship(back_populates="members")
