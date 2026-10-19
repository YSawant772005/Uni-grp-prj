"""ingestion run metrics and HTTP change-detection headers

Revision ID: b7f4d2c9a1e3
Revises: 590ecfb9963d
Create Date: 2026-10-19

Adds the counters the ingestion pipeline must report honestly (unchanged and
review-required records plus a last successful checkpoint) and the ETag /
Last-Modified validators used to detect that a source document has changed.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'b7f4d2c9a1e3'
down_revision: Union[str, None] = '590ecfb9963d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('ingestion_jobs',
                  sa.Column('records_unchanged', sa.Integer(), nullable=False,
                            server_default='0'))
    op.add_column('ingestion_jobs',
                  sa.Column('records_review_required', sa.Integer(), nullable=False,
                            server_default='0'))
    op.add_column('ingestion_jobs', sa.Column('checkpoint', postgresql.JSONB(), nullable=True))
    op.add_column('source_documents', sa.Column('etag', sa.String(length=200), nullable=True))
    op.add_column('source_documents', sa.Column('last_modified', sa.String(length=200),
                                                nullable=True))


def downgrade() -> None:
    op.drop_column('source_documents', 'last_modified')
    op.drop_column('source_documents', 'etag')
    op.drop_column('ingestion_jobs', 'checkpoint')
    op.drop_column('ingestion_jobs', 'records_review_required')
    op.drop_column('ingestion_jobs', 'records_unchanged')