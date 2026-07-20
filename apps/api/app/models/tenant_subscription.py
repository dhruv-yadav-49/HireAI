"""
app/models/tenant_subscription.py

Database model for commercial tenant subscriptions and quota limits.
CTO Refinements #3, #4:
  - Plan -> Invoice -> Usage -> Entitlements separation
  - References policy profiles for limits
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, String, Text, func, Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import SubscriptionPlan


class TenantSubscription(Base):
    """Stores tenant commercial subscriptions and quota policy limits."""

    __tablename__ = "tenant_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    plan: Mapped[SubscriptionPlan] = mapped_column(
        SQLEnum(SubscriptionPlan, name="subscription_plan", native_enum=False),
        default=SubscriptionPlan.FREE,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE", nullable=False)

    token_budget_monthly: Mapped[int] = mapped_column(Integer, default=100000, nullable=False)
    api_call_budget_monthly: Mapped[int] = mapped_column(Integer, default=5000, nullable=False)
    max_concurrent_jobs: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

    quota_policy_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    entitlements_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
