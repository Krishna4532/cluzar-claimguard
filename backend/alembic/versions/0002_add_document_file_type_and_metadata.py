"""add_document_file_type_and_metadata

Revision ID: 0002_add_doc_file_type_meta
Revises: 0001_initial_schema
Create Date: 2026-11-03 19:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0002_add_doc_file_type_meta'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    json_col_type = postgresql.JSONB(astext_type=sa.Text()) if bind.dialect.name == "postgresql" else sa.JSON()

    op.add_column(
        'documents',
        sa.Column('file_type', sa.String(length=16), server_default='txt', nullable=False)
    )
    op.add_column(
        'documents',
        sa.Column('metadata', json_col_type, server_default='{}', nullable=False)
    )
    op.create_index('ix_documents_file_type', 'documents', ['file_type'])


def downgrade() -> None:
    op.drop_index('ix_documents_file_type', table_name='documents')
    op.drop_column('documents', 'metadata')
    op.drop_column('documents', 'file_type')

