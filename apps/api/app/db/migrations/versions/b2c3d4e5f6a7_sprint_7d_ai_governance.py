"""
app/db/migrations/versions/b2c3d4e5f6a7_sprint_7d_ai_governance.py

Alembic migration for Sprint 7D: AI Governance Platform.
Creates 5 new tables:
  1. governance_policies
  2. governance_decisions
  3. governance_approvals
  4. compliance_reports
  5. policy_violations

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-19 13:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. governance_policies
    op.create_table(
        'governance_policies',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('pack_type', sa.String(length=50), nullable=False, server_default='DEFAULT'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rules_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_governance_policies_organization_id'), 'governance_policies', ['organization_id'], unique=False)

    # 2. governance_decisions
    op.create_table(
        'governance_decisions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('ai_job_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action_type', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=100), nullable=True),
        sa.Column('action_payload_hash', sa.String(length=64), nullable=True),
        sa.Column('risk_score', sa.Float(), nullable=False),
        sa.Column('risk_level', sa.String(length=50), nullable=False),
        sa.Column('decision_status', sa.String(length=50), nullable=False),
        sa.Column('explanation_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('decision_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('risk_model_version', sa.String(length=20), nullable=False, server_default='1.0'),
        sa.Column('policy_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('policy_name', sa.String(length=200), nullable=True),
        sa.Column('request_id', sa.String(length=100), nullable=True),
        sa.Column('correlation_id', sa.String(length=100), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_governance_decisions_organization_id'), 'governance_decisions', ['organization_id'], unique=False)
    op.create_index(op.f('ix_governance_decisions_action_type'), 'governance_decisions', ['action_type'], unique=False)
    op.create_index(op.f('ix_governance_decisions_decided_at'), 'governance_decisions', ['decided_at'], unique=False)

    # 3. governance_approvals
    op.create_table(
        'governance_approvals',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('governance_decision_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('requested_to', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('leased_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('lease_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='PENDING'),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('approver_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['governance_decision_id'], ['governance_decisions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_governance_approvals_governance_decision_id'), 'governance_approvals', ['governance_decision_id'], unique=False)
    op.create_index(op.f('ix_governance_approvals_organization_id'), 'governance_approvals', ['organization_id'], unique=False)
    op.create_index(op.f('ix_governance_approvals_expires_at'), 'governance_approvals', ['expires_at'], unique=False)

    # 4. compliance_reports
    op.create_table(
        'compliance_reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('framework', sa.String(length=50), nullable=False),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('total_decisions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('permitted_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('blocked_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('escalated_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('approved_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('rejected_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('score', sa.Float(), nullable=False, server_default='100.0'),
        sa.Column('controls_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('violations_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_compliance_reports_organization_id'), 'compliance_reports', ['organization_id'], unique=False)

    # 5. policy_violations
    op.create_table(
        'policy_violations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('governance_decision_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('framework', sa.String(length=50), nullable=False),
        sa.Column('control_id', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('remediation_hint', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['governance_decision_id'], ['governance_decisions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_policy_violations_organization_id'), 'policy_violations', ['organization_id'], unique=False)
    op.create_index(op.f('ix_policy_violations_governance_decision_id'), 'policy_violations', ['governance_decision_id'], unique=False)


def downgrade() -> None:
    op.drop_table('policy_violations')
    op.drop_table('compliance_reports')
    op.drop_table('governance_approvals')
    op.drop_table('governance_decisions')
    op.drop_table('governance_policies')
