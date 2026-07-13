import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, Integer, Float, String, Text, Index, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, BaseModel
from app.models.enums import AIProvider


class AIProviderConfig(Base):
    """Configuration credentials setup for external LLM APIs (OpenAI, Gemini, etc.) per tenant."""

    __tablename__ = "ai_provider_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[AIProvider] = mapped_column(
        SQLEnum(AIProvider, name="ai_provider", native_enum=False),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Store credentials (e.g. API keys) safely
    credentials_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    configuration_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    health_status: Mapped[str] = mapped_column(String(50), default="UNKNOWN", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index(
            "uq_default_ai_provider",
            "organization_id",
            "provider",
            unique=True,
            postgresql_where="is_default = true AND enabled = true",
        ),
    )


class AIAgent(BaseModel):
    """AI Agent config settings representing customized AI Employee instructions."""

    __tablename__ = "ai_agents"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)

    # Modular defaults
    default_prompt_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_prompts.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_provider_configs.id", ondelete="SET NULL"),
        nullable=True,
    )

    provider: Mapped[AIProvider] = mapped_column(
        SQLEnum(AIProvider, name="ai_provider", native_enum=False),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    temperature: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, default=2048, nullable=False)

    supports_tools: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    supports_streaming: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    supports_memory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
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
