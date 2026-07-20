"""
app/models/marketplace_publisher.py

Database model for verified marketplace publisher profiles.
CTO Refinement #7:
  Persists publisher identity & trust fields:
  verified_since, support_contact, organization, website, verification_badge
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SQLEnum, String, Text, func, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import PublisherVerificationBadge


class MarketplacePublisher(Base):
    """Stores verified publisher profiles and trust credentials."""

    __tablename__ = "marketplace_publishers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    publisher_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    bio: Mapped[str] = mapped_column(Text, nullable=False)

    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verification_badge: Mapped[PublisherVerificationBadge] = mapped_column(
        SQLEnum(PublisherVerificationBadge, name="publisher_verification_badge", native_enum=False),
        default=PublisherVerificationBadge.COMMUNITY_CONTRIBUTOR,
        nullable=False,
    )

    # Trust & Contact fields (CTO #7)
    verified_since: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    support_contact: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    organization: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
