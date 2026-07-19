import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum

from app.db.base import Base
from app.models.enums import SecurityPolicyStatus


class SecurityPolicy(Base):
    """Per-organization security policy rules.

    ADR-021: Tenant Isolation — every org has independent policy evaluation.
    CTO refinement #10: supports inheritance — default policy is loaded when
    no org-specific policy exists.
    """
    __tablename__ = "security_policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # NULL organization_id = global default policy (inherited by all orgs)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    policy_name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Rules JSON: {
    #   "allowed_auth_methods": ["JWT", "API_KEY"],
    #   "rate_limit_rpm": 1000,
    #   "allowed_models": ["gpt-4o"],
    #   "pii_enforcement": true,
    #   "require_mfa": false,
    #   "ip_allowlist": []
    # }
    rules_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    status: Mapped[SecurityPolicyStatus] = mapped_column(
        SQLEnum(
            SecurityPolicyStatus,
            name="security_policy_status",
            native_enum=False,
            create_constraint=False,
        ),
        nullable=False,
        default=SecurityPolicyStatus.ACTIVE,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
