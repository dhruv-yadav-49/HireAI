import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import ForecastPeriod


class AIForecast(Base):
    """Stores generated business analyst revenue and conversion predictions."""

    __tablename__ = "ai_forecasts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    forecast_period: Mapped[ForecastPeriod] = mapped_column(
        SQLEnum(ForecastPeriod, name="forecast_period", native_enum=False),
        nullable=False,
    )
    predicted_revenue: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00, nullable=False)
    predicted_conversion_rate: Mapped[float] = mapped_column(Numeric(5, 4), default=0.0000, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Numeric(3, 2), default=1.00, nullable=False)
    
    forecast_model: Mapped[str] = mapped_column(String(100), default="RULE_BASED", nullable=False)
    forecast_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    training_period: Mapped[str | None] = mapped_column(String(100), nullable=True)
    assumptions_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    forecast_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
