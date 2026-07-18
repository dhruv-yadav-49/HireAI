import uuid
from sqlalchemy import Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

from app.db.base import Base
from app.models.enums import EvaluationMetric


class AIEvaluationMetric(Base):
    """Stores individual scores and weights for evaluated metric types.

    CTO refinement #2: details_json has inputs, outputs, score, explanation, warnings.
    """
    __tablename__ = "ai_evaluation_metrics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_evaluations.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    metric_type: Mapped[EvaluationMetric] = mapped_column(
        SQLEnum(EvaluationMetric, name="evaluation_metric", native_enum=False, create_constraint=False),
        nullable=False
    )

    score: Mapped[float] = mapped_column(Float, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)

    # Standardized: {inputs, outputs, score, explanation, warnings}
    details_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
