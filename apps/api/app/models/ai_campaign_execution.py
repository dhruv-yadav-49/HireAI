import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import CampaignStatus


class AICampaignExecution(Base):
    """Stores campaign execution records, audience snapshots, and statistics segmentations."""

    __tablename__ = "ai_campaign_executions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )
    segment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_audience_segments.id", ondelete="SET NULL"),
        nullable=True,
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[CampaignStatus] = mapped_column(
        SQLEnum(CampaignStatus, name="campaign_status", native_enum=False),
        nullable=False,
        default=CampaignStatus.DRAFT,
    )
    
    audience_snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    statistics_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    attribution_model: Mapped[str] = mapped_column(String(50), default="LAST_TOUCH", nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
