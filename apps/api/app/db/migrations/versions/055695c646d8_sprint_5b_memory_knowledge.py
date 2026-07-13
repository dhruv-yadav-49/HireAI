"""sprint_5b_memory_knowledge

Revision ID: 055695c646d8
Revises: 83e1c561e884
Create Date: 2026-07-14 00:21:09.123696

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '055695c646d8'
down_revision: Union[str, Sequence[str], None] = '83e1c561e884'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ── Deploy PL/pgSQL cosine similarity fallback function ──
    op.execute("""
    CREATE OR REPLACE FUNCTION public.cosine_similarity(a REAL[], b REAL[])
    RETURNS DOUBLE PRECISION AS $$
    DECLARE
        dot_product DOUBLE PRECISION := 0;
        norm_a DOUBLE PRECISION := 0;
        norm_b DOUBLE PRECISION := 0;
        i INT;
    BEGIN
        IF array_length(a, 1) != array_length(b, 1) THEN
            RETURN 0;
        END IF;
        FOR i IN 1..array_length(a, 1) LOOP
            dot_product := dot_product + (a[i] * b[i]);
            norm_a := norm_a + (a[i] * a[i]);
            norm_b := norm_b + (b[i] * b[i]);
        END LOOP;
        IF norm_a = 0 OR norm_b = 0 THEN
            RETURN 0;
        END IF;
        RETURN dot_product / (sqrt(norm_a) * sqrt(norm_b));
    END;
    $$ LANGUAGE plpgsql IMMUTABLE;
    """)

    # ── Create tables ──
    op.create_table('knowledge_documents',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('source_type', sa.String(length=50), nullable=False),
    sa.Column('mime_type', sa.String(length=100), nullable=False),
    sa.Column('file_size', sa.Integer(), nullable=False),
    sa.Column('storage_path', sa.String(length=500), nullable=False),
    sa.Column('checksum_sha256', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('embedding_provider', sa.String(length=50), nullable=False),
    sa.Column('embedding_model', sa.String(length=100), nullable=False),
    sa.Column('chunk_count', sa.Integer(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('processing_error', sa.Text(), nullable=True),
    sa.Column('processing_started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('processing_finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('updated_by', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('knowledge_chunks',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('document_id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('chunk_index', sa.Integer(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('token_count', sa.Integer(), nullable=False),
    sa.Column('embedding_status', sa.String(length=50), nullable=False),
    sa.Column('embedding_vector_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['knowledge_documents.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('embeddings',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('chunk_id', sa.UUID(), nullable=False),
    sa.Column('provider', sa.String(length=50), nullable=False),
    sa.Column('provider_model', sa.String(length=100), nullable=False),
    sa.Column('dimensions', sa.Integer(), nullable=False),
    sa.Column('embedding_schema_version', sa.Integer(), nullable=False),
    sa.Column('embedding_model_version', sa.Integer(), nullable=False),
    sa.Column('checksum_sha256', sa.String(length=64), nullable=False),
    sa.Column('vector', postgresql.ARRAY(sa.Float()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['chunk_id'], ['knowledge_chunks.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('ai_memories',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('conversation_id', sa.UUID(), nullable=True),
    sa.Column('lead_id', sa.UUID(), nullable=True),
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('scope', sa.String(length=50), nullable=False),
    sa.Column('memory_type', sa.String(length=50), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('importance_score', sa.Numeric(precision=4, scale=3), nullable=False),
    sa.Column('confidence_score', sa.Numeric(precision=4, scale=3), nullable=False),
    sa.Column('memory_version', sa.Integer(), nullable=False),
    sa.Column('source', sa.String(length=50), nullable=False),
    sa.Column('supersedes_memory_id', sa.UUID(), nullable=True),
    sa.Column('last_accessed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['ai_conversations.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['supersedes_memory_id'], ['ai_memories.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('retrieval_logs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('conversation_id', sa.UUID(), nullable=True),
    sa.Column('query', sa.Text(), nullable=False),
    sa.Column('query_embedding_id', sa.UUID(), nullable=True),
    sa.Column('retrieval_source', sa.String(length=50), nullable=False),
    sa.Column('retrieved_chunks', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('retrieval_latency_ms', sa.Integer(), nullable=False),
    sa.Column('embedding_latency_ms', sa.Integer(), nullable=False),
    sa.Column('vector_search_latency_ms', sa.Integer(), nullable=False),
    sa.Column('crm_latency_ms', sa.Integer(), nullable=False),
    sa.Column('memory_latency_ms', sa.Integer(), nullable=False),
    sa.Column('rerank_latency_ms', sa.Integer(), nullable=False),
    sa.Column('total_chunks', sa.Integer(), nullable=False),
    sa.Column('total_tokens', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['ai_conversations.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('retrieval_feedbacks',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('log_id', sa.UUID(), nullable=False),
    sa.Column('user_feedback', sa.String(length=50), nullable=False),
    sa.Column('feedback_text', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['log_id'], ['retrieval_logs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('retrieval_feedbacks')
    op.drop_table('retrieval_logs')
    op.drop_table('ai_memories')
    op.drop_table('embeddings')
    op.drop_table('knowledge_chunks')
    op.drop_table('knowledge_documents')
    
    op.execute("DROP FUNCTION IF EXISTS public.cosine_similarity(REAL[], REAL[]);")
