"""
d5e6f7a8b9c0_sprint_8b_marketplace_experience.py

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-07-20 16:50:00.000000

Sprint 8B: Marketplace Experience & Resolver.
Creates marketplace_reviews, marketplace_publishers, and agent_package_versions tables.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. marketplace_reviews
    op.create_table(
        'marketplace_reviews',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('package_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('review_text', sa.Text(), nullable=False),
        sa.Column('runtime_version', sa.String(length=50), nullable=False, server_default='1.0.0'),
        sa.Column('package_version', sa.String(length=50), nullable=False, server_default='1.0.0'),
        sa.Column('organization_type', sa.String(length=50), nullable=False, server_default='ENTERPRISE'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['package_id'], ['marketplace_packages.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 2. marketplace_publishers
    op.create_table(
        'marketplace_publishers',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('publisher_name', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('bio', sa.Text(), nullable=False),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('verification_badge', sa.String(length=50), nullable=False, server_default='COMMUNITY_CONTRIBUTOR'),
        sa.Column('verified_since', sa.DateTime(timezone=True), nullable=True),
        sa.Column('support_contact', sa.String(length=255), nullable=True),
        sa.Column('organization', sa.String(length=100), nullable=True),
        sa.Column('website', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('publisher_name')
    )

    # 3. agent_package_versions
    op.create_table(
        'agent_package_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('package_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version', sa.String(length=50), nullable=False),
        sa.Column('channel', sa.String(length=50), nullable=False, server_default='STABLE'),
        sa.Column('manifest_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('changelog', sa.Text(), nullable=False, server_default='Initial release'),
        sa.Column('released_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['package_id'], ['marketplace_packages.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('agent_package_versions')
    op.drop_table('marketplace_publishers')
    op.drop_table('marketplace_reviews')
