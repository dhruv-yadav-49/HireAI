from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func


class TimestampMixin:
    """created_at is set once by the DB. updated_at is bumped by the DB on
    every UPDATE (onupdate=func.now()) -- so services never need to
    remember to set it manually."""

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )


class SoftDeleteMixin:
    """Adds deleted_at. This mixin does NOT automatically filter queries --
    SQLAlchemy has no global "default scope" like some ORMs. Every
    repository method that reads rows must explicitly filter
    `WHERE deleted_at IS NULL`. See OrganizationRepository for the pattern.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
