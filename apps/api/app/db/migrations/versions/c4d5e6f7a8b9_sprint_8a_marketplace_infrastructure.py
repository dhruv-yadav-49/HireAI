"""
c4d5e6f7a8b9_sprint_8a_marketplace_infrastructure.py

Revision ID: c4d5e6f7a8b9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-20 16:40:00.000000

Sprint 8A: Agent Marketplace Platform Infrastructure.
Creates marketplace_packages, agent_installations, and agent_compatibility_logs tables.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. marketplace_packages
    op.create_table(
        'marketplace_packages',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('package_name', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('author', sa.String(length=100), nullable=False),
        sa.Column('package_type', sa.String(length=50), nullable=False, server_default='COMMUNITY'),
        sa.Column('version', sa.String(length=50), nullable=False, server_default='1.0.0'),
        sa.Column('manifest_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('api_version', sa.String(length=50), nullable=False, server_default='1.0'),
        sa.Column('sdk_version', sa.String(length=50), nullable=False, server_default='>=1.0'),
        sa.Column('runtime_requirement', sa.String(length=50), nullable=False, server_default='>=1.0'),
        sa.Column('stable_version', sa.String(length=50), nullable=True),
        sa.Column('beta_version', sa.String(length=50), nullable=True),
        sa.Column('latest_version', sa.String(length=50), nullable=False, server_default='1.0.0'),
        sa.Column('manifest_yaml', sa.Text(), nullable=False),
        sa.Column('manifest_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('package_hash', sa.String(length=64), nullable=False),
        sa.Column('signature', sa.Text(), nullable=True),
        sa.Column('publisher_id', sa.String(length=100), nullable=True),
        sa.Column('certificate_id', sa.String(length=100), nullable=True),
        sa.Column('lifecycle_status', sa.String(length=50), nullable=False, server_default='DRAFT'),
        sa.Column('validation_results_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('package_name')
    )

    # 2. agent_installations
    op.create_table(
        'agent_installations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('package_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_key', sa.String(length=100), nullable=False),
        sa.Column('current_version', sa.String(length=50), nullable=False),
        sa.Column('previous_version', sa.String(length=50), nullable=True),
        sa.Column('installed_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='PENDING'),
        sa.Column('config_overrides_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('verification_results_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('installed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['package_id'], ['marketplace_packages.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['installed_by'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 3. agent_compatibility_logs
    op.create_table(
        'agent_compatibility_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('package_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_key', sa.String(length=100), nullable=False),
        sa.Column('compatible', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('check_type', sa.String(length=50), nullable=False),
        sa.Column('details_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['package_id'], ['marketplace_packages.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('agent_compatibility_logs')
    op.drop_table('agent_installations')
    op.drop_table('marketplace_packages')
