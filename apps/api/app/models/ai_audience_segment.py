import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AudienceType


class AIAudienceSegment(Base):
    """Stores audience segments representing dynamic or static filters of leads."""

    __tablename__ = "ai_audience_segments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    segment_type: Mapped[AudienceType] = mapped_column(
        SQLEnum(AudienceType, name="audience_type", native_enum=False),
        nullable=False,
    )
    criteria_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    estimated_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    segment_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    generated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
