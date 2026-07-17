import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import CampaignType, CampaignGoal, CampaignStatus, CampaignPriority


class AICampaign(Base):
    """Stores AI-planned marketing campaigns with strategy and versioning support."""

    __tablename__ = "ai_campaigns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    campaign_type: Mapped[CampaignType] = mapped_column(
        SQLEnum(CampaignType, name="campaign_type", native_enum=False),
        nullable=False,
    )
    campaign_goal: Mapped[CampaignGoal] = mapped_column(
        SQLEnum(CampaignGoal, name="campaign_goal", native_enum=False),
        nullable=False,
    )
    status: Mapped[CampaignStatus] = mapped_column(
        SQLEnum(CampaignStatus, name="campaign_status", native_enum=False),
        nullable=False,
        default=CampaignStatus.DRAFT,
    )
    priority: Mapped[CampaignPriority] = mapped_column(
        SQLEnum(CampaignPriority, name="campaign_priority", native_enum=False),
        nullable=False,
        default=CampaignPriority.MEDIUM,
    )
    strategy_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    
    campaign_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    parent_campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_campaigns.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
