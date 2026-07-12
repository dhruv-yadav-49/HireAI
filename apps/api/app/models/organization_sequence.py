import uuid

from sqlalchemy import ForeignKey, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OrganizationSequence(Base):
    """Sequence generator per organization to generate concurrency-safe,
    non-colliding, tenant-isolated sequential lead numbers.
    """

    __tablename__ = "organization_sequences"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    next_lead_number: Mapped[int] = mapped_column(BigInteger, default=1001, nullable=False)
