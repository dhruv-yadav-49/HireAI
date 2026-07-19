"""sprint_7c_enterprise_security

Revision ID: a1b2c3d4e5f6
Revises: 9bbbd28b17b0
Create Date: 2026-07-18 18:15:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "9bbbd28b17b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── api_keys ────────────────────────────────────────────────────────────────
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("hashed_key", sa.String(64), nullable=False),
        sa.Column("prefix", sa.String(20), nullable=False),
        sa.Column("scopes_json", postgresql.JSONB(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_from", sa.String(100), nullable=True),
        sa.Column("last_ip", sa.String(45), nullable=True),
        sa.Column("last_user_agent", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hashed_key"),
    )
    op.create_index(op.f("ix_api_keys_organization_id"), "api_keys", ["organization_id"])
    op.create_index(op.f("ix_api_keys_prefix"), "api_keys", ["prefix"])
    op.create_index(op.f("ix_api_keys_user_id"), "api_keys", ["user_id"])

    # ── security_policies ───────────────────────────────────────────────────────
    op.create_table(
        "security_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("policy_name", sa.String(200), nullable=False),
        sa.Column("rules_json", postgresql.JSONB(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_security_policies_organization_id"),
        "security_policies",
        ["organization_id"],
    )

    # ── audit_logs ──────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=True),
        sa.Column("resource_id", sa.String(200), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("request_id", sa.String(100), nullable=True),
        sa.Column("correlation_id", sa.String(100), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_organization_id"), "audit_logs", ["organization_id"])
    op.create_index(op.f("ix_audit_logs_user_id"), "audit_logs", ["user_id"])
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"])
    op.create_index(op.f("ix_audit_logs_request_id"), "audit_logs", ["request_id"])
    op.create_index(op.f("ix_audit_logs_correlation_id"), "audit_logs", ["correlation_id"])
    op.create_index(op.f("ix_audit_logs_created_at"), "audit_logs", ["created_at"])

    # ── pii_incidents ───────────────────────────────────────────────────────────
    op.create_table(
        "pii_incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pii_type", sa.String(20), nullable=False),
        sa.Column("location", sa.String(500), nullable=False),
        sa.Column("severity", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("masked", sa.Boolean(), nullable=False),
        sa.Column("request_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pii_incidents_organization_id"), "pii_incidents", ["organization_id"])
    op.create_index(op.f("ix_pii_incidents_pii_type"), "pii_incidents", ["pii_type"])
    op.create_index(op.f("ix_pii_incidents_request_id"), "pii_incidents", ["request_id"])
    op.create_index(op.f("ix_pii_incidents_created_at"), "pii_incidents", ["created_at"])

    # ── secret_references ───────────────────────────────────────────────────────
    op.create_table(
        "secret_references",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("secret_name", sa.String(300), nullable=False),
        sa.Column("secret_type", sa.String(20), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("rotation_period_days", sa.Integer(), nullable=True),
        sa.Column("last_rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_secret_references_organization_id"), "secret_references", ["organization_id"]
    )
    op.create_index(
        op.f("ix_secret_references_secret_name"), "secret_references", ["secret_name"]
    )


def downgrade() -> None:
    op.drop_table("secret_references")
    op.drop_table("pii_incidents")
    op.drop_table("audit_logs")
    op.drop_table("security_policies")
    op.drop_table("api_keys")
