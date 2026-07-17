import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AIKPISnapshot(Base):
    """Stores immutable historical snapshots of calculated business KPIs."""

    __tablename__ = "ai_kpi_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    snapshot_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    total_leads: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    qualified_leads: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    won_deals: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lost_deals: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pipeline_value: Mapped[float] = mapped_column(Numeric(12, 2), default=0.00, nullable=False)
    conversion_rate: Mapped[float] = mapped_column(Numeric(5, 4), default=0.0000, nullable=False)
    average_sales_cycle: Mapped[float] = mapped_column(Numeric(6, 2), default=0.00, nullable=False)
    average_response_time: Mapped[float] = mapped_column(Numeric(6, 2), default=0.00, nullable=False)
    
    snapshot_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    calculation_duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
