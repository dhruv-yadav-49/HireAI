"""
app/db/migrations/versions/c3d4e5f6a7b8_sprint_7e_ai_playground.py

Alembic migration for Sprint 7E: AI Playground Platform.
Creates 3 new tables:
  1. playground_sessions
  2. playground_experiments
  3. prompt_experiments

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-19 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. playground_sessions
    op.create_table(
        'playground_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False, server_default='Playground Session'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='ACTIVE'),
        sa.Column('isolation_level', sa.String(length=50), nullable=False, server_default='READ_ONLY'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_playground_sessions_organization_id'), 'playground_sessions', ['organization_id'], unique=False)
    op.create_index(op.f('ix_playground_sessions_user_id'), 'playground_sessions', ['user_id'], unique=False)

    # 2. playground_experiments
    op.create_table(
        'playground_experiments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('experiment_name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='DRAFT'),
        sa.Column('comparison_type', sa.String(length=50), nullable=False, server_default='PROMPT'),
        sa.Column('matrix_config_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['session_id'], ['playground_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_playground_experiments_session_id'), 'playground_experiments', ['session_id'], unique=False)
    op.create_index(op.f('ix_playground_experiments_organization_id'), 'playground_experiments', ['organization_id'], unique=False)

    # 3. prompt_experiments
    op.create_table(
        'prompt_experiments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('experiment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('prompt_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('experiment_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('runtime_version', sa.String(length=20), nullable=False, server_default='1.0'),
        sa.Column('provider_version', sa.String(length=20), nullable=False, server_default='1.0'),
        sa.Column('prompt_hash', sa.String(length=64), nullable=False),
        sa.Column('compiled_prompt_hash', sa.String(length=64), nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=False),
        sa.Column('temperature', sa.Float(), nullable=False, server_default='0.7'),
        sa.Column('max_tokens', sa.Integer(), nullable=False, server_default='1000'),
        sa.Column('prompt_text', sa.Text(), nullable=False),
        sa.Column('output_text', sa.Text(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('token_cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('evaluation_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('governance_decision', sa.String(length=50), nullable=True),
        sa.Column('normalized_metrics_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['experiment_id'], ['playground_experiments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_prompt_experiments_experiment_id'), 'prompt_experiments', ['experiment_id'], unique=False)


def downgrade() -> None:
    op.drop_table('prompt_experiments')
    op.drop_table('playground_experiments')
    op.drop_table('playground_sessions')
