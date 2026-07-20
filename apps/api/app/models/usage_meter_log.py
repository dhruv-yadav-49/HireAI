"""
app/models/usage_meter_log.py

Database model for generic metered usage events.
CTO Refinement #2:
  Meters: AI tokens, API calls, agent tasks, LLM cost, workflow executions,
  tool invocations, playground sessions, marketplace downloads, storage MB
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import MeteredMetricType


class UsageMeterLog(Base):
    """Stores individual metered usage events for commercial accounting."""

    __tablename__ = "usage_meter_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    metric_type: Mapped[MeteredMetricType] = mapped_column(
        SQLEnum(MeteredMetricType, name="metered_metric_type", native_enum=False),
        nullable=False,
    )
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    cost_units: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
