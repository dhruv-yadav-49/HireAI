import uuid
from sqlalchemy import Enum as SQLEnum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import ABTestStatus


class AIABTest(Base):
    """Stores configured campaign copy experiments and metrics outcomes."""

    __tablename__ = "ai_ab_tests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )
    variants_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    winner: Mapped[str | None] = mapped_column(String(50), nullable=True)
    winner_metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    metrics_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[ABTestStatus] = mapped_column(
        SQLEnum(ABTestStatus, name="ab_test_status", native_enum=False),
        nullable=False,
        default=ABTestStatus.DRAFT,
    )
