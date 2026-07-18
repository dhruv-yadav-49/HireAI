import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Float, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

from app.db.base import Base
from app.models.enums import EvaluationMetric, QualityRuleAction


class AIQualityRule(Base):
    """Configures thresholds for specific metrics with defined response actions.

    CTO refinement #9: actions can be WARN, FAIL, BLOCK, or NOTIFY.
    """
    __tablename__ = "ai_quality_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    rule_name: Mapped[str] = mapped_column(String(200), nullable=False)
    metric_type: Mapped[EvaluationMetric] = mapped_column(
        SQLEnum(EvaluationMetric, name="evaluation_metric", native_enum=False, create_constraint=False),
        nullable=False
    )
    threshold: Mapped[float] = mapped_column(Float, nullable=False)  # Minimum acceptable score (e.g. 0.85)

    action: Mapped[QualityRuleAction] = mapped_column(
        SQLEnum(QualityRuleAction, name="quality_rule_action", native_enum=False, create_constraint=False),
        nullable=False,
        default=QualityRuleAction.WARN
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
