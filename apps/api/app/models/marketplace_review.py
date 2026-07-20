"""
app/models/marketplace_review.py

Database model for marketplace user ratings and reviews.
CTO Refinement #5:
  Persists review metadata: rating, review, runtime_version, package_version, organization_type
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MarketplaceReview(Base):
    """Stores user reviews and ratings with version metadata."""

    __tablename__ = "marketplace_reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marketplace_packages.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 to 5 stars
    review_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Metadata (CTO #5)
    runtime_version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)
    package_version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)
    organization_type: Mapped[str] = mapped_column(String(50), default="ENTERPRISE", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
