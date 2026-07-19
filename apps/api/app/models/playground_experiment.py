"""
app/models/playground_experiment.py

PlaygroundExperiment model grouping trials & matrix runs.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

from app.db.base import Base
from app.models.enums import ComparisonType, ExperimentStatus


class PlaygroundExperiment(Base):
    """Container for single or matrix prompt / model / governance experiments."""

    __tablename__ = "playground_experiments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("playground_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    experiment_name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[ExperimentStatus] = mapped_column(
        SQLEnum(
            ExperimentStatus,
            name="experiment_status",
            native_enum=False,
            create_constraint=False,
        ),
        nullable=False,
        default=ExperimentStatus.DRAFT,
    )

    comparison_type: Mapped[ComparisonType] = mapped_column(
        SQLEnum(
            ComparisonType,
            name="comparison_type",
            native_enum=False,
            create_constraint=False,
        ),
        nullable=False,
        default=ComparisonType.PROMPT,
    )

    matrix_config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
