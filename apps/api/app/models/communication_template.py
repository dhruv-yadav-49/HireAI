import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel
from app.models.enums import CommunicationChannel


class CommunicationTemplate(BaseModel):
    """Stores reusable templates for dynamic channels (EMAIL, WHATSAPP, SMS) with placeholders."""

    __tablename__ = "communication_templates"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    channel: Mapped[CommunicationChannel] = mapped_column(
        SQLEnum(CommunicationChannel, name="communication_channel", native_enum=False),
        nullable=False,
    )
    subject_template: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Store list of variables parsed (e.g. ["lead.first_name"])
    variables_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    updated_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    __table_args__ = (
        Index(
            "uq_communication_templates",
            "organization_id",
            "name",
            "channel",
            unique=True,
            postgresql_where="deleted_at IS NULL",
        ),
    )
