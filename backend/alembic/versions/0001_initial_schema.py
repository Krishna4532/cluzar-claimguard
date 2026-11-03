"""create_initial_schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-11-03 18:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector
from app.core.config import settings

# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable pgvector extension if running on PostgreSQL
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Businesses
    op.create_table(
        'businesses',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('business_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('industry', sa.String(length=128), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=False, server_default='INR'),
        sa.Column('timezone', sa.String(length=64), nullable=False, server_default='Asia/Kolkata'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('business_id')
    )
    op.create_index('ix_businesses_business_id', 'businesses', ['business_id'], unique=True)

    # 3. Documents
    op.create_table(
        'documents',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('document_id', sa.String(length=64), nullable=False),
        sa.Column('business_id', sa.Integer(), nullable=False),
        sa.Column('document_type', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id')
    )
    op.create_index('ix_documents_document_id', 'documents', ['document_id'], unique=True)
    op.create_index('ix_documents_business_id', 'documents', ['business_id'])
    op.create_index('ix_documents_document_type', 'documents', ['document_type'])
    op.create_index('ix_documents_content_hash', 'documents', ['content_hash'])
    op.create_index('ix_documents_status', 'documents', ['status'])
    op.create_index('ix_documents_biz_status', 'documents', ['business_id', 'status'])
    op.create_index('ix_documents_biz_type', 'documents', ['business_id', 'document_type'])

    # 4. Drafts
    op.create_table(
        'drafts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('business_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_drafts_business_id', 'drafts', ['business_id'])
    op.create_index('ix_drafts_status', 'drafts', ['status'])
    op.create_index('ix_drafts_biz_status', 'drafts', ['business_id', 'status'])

    # 5. Claims
    op.create_table(
        'claims',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('draft_id', sa.Integer(), nullable=False),
        sa.Column('claim_text', sa.Text(), nullable=False),
        sa.Column('claim_type', sa.String(length=64), nullable=False),
        sa.Column('start_char', sa.Integer(), nullable=False),
        sa.Column('end_char', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['draft_id'], ['drafts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_claims_draft_id', 'claims', ['draft_id'])
    op.create_index('ix_claims_claim_type', 'claims', ['claim_type'])
    op.create_index('ix_claims_draft_type', 'claims', ['draft_id', 'claim_type'])

    # 6. Document Chunks
    json_col_type = postgresql.JSONB(astext_type=sa.Text()) if bind.dialect.name == "postgresql" else sa.JSON()
    op.create_table(
        'document_chunks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('start_char', sa.Integer(), nullable=False),
        sa.Column('end_char', sa.Integer(), nullable=False),
        sa.Column('metadata', json_col_type, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id', 'chunk_index', name='uq_document_chunk_index')
    )
    op.create_index('ix_document_chunks_document_id', 'document_chunks', ['document_id'])
    op.create_index('ix_chunks_doc_chunk_idx', 'document_chunks', ['document_id', 'chunk_index'])

    # 7. Structured Facts
    op.create_table(
        'structured_facts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('business_id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=True),
        sa.Column('fact_type', sa.String(length=64), nullable=False),
        sa.Column('subject', sa.String(length=255), nullable=False),
        sa.Column('predicate', sa.String(length=128), nullable=False),
        sa.Column('value', json_col_type, nullable=False),
        sa.Column('conditions', json_col_type, nullable=True),
        sa.Column('validity_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('validity_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_structured_facts_business_id', 'structured_facts', ['business_id'])
    op.create_index('ix_structured_facts_document_id', 'structured_facts', ['document_id'])
    op.create_index('ix_structured_facts_fact_type', 'structured_facts', ['fact_type'])
    op.create_index('ix_structured_facts_subject', 'structured_facts', ['subject'])
    op.create_index('ix_structured_facts_predicate', 'structured_facts', ['predicate'])
    op.create_index('ix_facts_biz_type_subj', 'structured_facts', ['business_id', 'fact_type', 'subject'])
    op.create_index('ix_facts_subj_predicate', 'structured_facts', ['subject', 'predicate'])

    # 8. Embeddings (Vector dimension 384 for sentence-transformers/all-MiniLM-L6-v2)
    vector_type = Vector(settings.EMBEDDING_DIMENSION) if bind.dialect.name == "postgresql" else sa.JSON()
    op.create_table(
        'embeddings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('chunk_id', sa.Integer(), nullable=False),
        sa.Column('embedding', vector_type, nullable=False),
        sa.Column('embedding_model', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['chunk_id'], ['document_chunks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_embeddings_chunk_id', 'embeddings', ['chunk_id'])

    # 9. Verifications
    op.create_table(
        'verifications',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('claim_id', sa.Integer(), nullable=False),
        sa.Column('verdict', sa.String(length=32), nullable=False),
        sa.Column('rationale', sa.Text(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['claim_id'], ['claims.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_verifications_claim_id', 'verifications', ['claim_id'])
    op.create_index('ix_verifications_verdict', 'verifications', ['verdict'])
    op.create_index('ix_verifications_claim_created', 'verifications', ['claim_id', 'created_at'])

    # 10. Human Reviews
    op.create_table(
        'human_reviews',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('verification_id', sa.Integer(), nullable=False),
        sa.Column('reviewer_decision', sa.String(length=64), nullable=False),
        sa.Column('reviewer_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['verification_id'], ['verifications.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_human_reviews_verification_id', 'human_reviews', ['verification_id'])

    # 11. Verification Evidence
    op.create_table(
        'verification_evidence',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('verification_id', sa.Integer(), nullable=False),
        sa.Column('chunk_id', sa.Integer(), nullable=True),
        sa.Column('relevance_score', sa.Float(), nullable=True),
        sa.Column('evidence_text', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['chunk_id'], ['document_chunks.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['verification_id'], ['verifications.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_verification_evidence_verification_id', 'verification_evidence', ['verification_id'])
    op.create_index('ix_verification_evidence_chunk_id', 'verification_evidence', ['chunk_id'])


def downgrade() -> None:
    op.drop_table('verification_evidence')
    op.drop_table('human_reviews')
    op.drop_table('verifications')
    op.drop_table('embeddings')
    op.drop_table('structured_facts')
    op.drop_table('document_chunks')
    op.drop_table('claims')
    op.drop_table('drafts')
    op.drop_table('documents')
    op.drop_table('businesses')
