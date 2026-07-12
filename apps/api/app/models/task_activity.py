import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, SmallInteger
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.models.enums import ActorType, TaskActivityType


class TaskActivity(Base):
    """Immutable timeline activity logs for tasks.

    Never updated or deleted (append-only timeline rule).
    """

    __tablename__ = "task_activities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_type: Mapped[ActorType] = mapped_column(
        SQLEnum(ActorType, name="actor_type", native_enum=False),
        nullable=False,
        default=ActorType.USER,
    )
    activity_type: Mapped[TaskActivityType] = mapped_column(
        SQLEnum(TaskActivityType, name="task_activity_type", native_enum=False),
        nullable=False,
    )
    event_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    metadata_version: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=1
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    task = relationship("Task", back_populates="activities")
    actor = relationship("User")
