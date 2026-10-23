"""Separate, source-versioned ROR reference directory; no catalogue changes."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '9c24a7e6d180'
down_revision = '85b2e4a6c910'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('directory_releases',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('source_document_id', sa.Uuid(), sa.ForeignKey('source_documents.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('manifest', postgresql.JSONB(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table('directory_institutions',
        sa.Column('release_id', sa.String(64), sa.ForeignKey('directory_releases.id', ondelete='RESTRICT'), primary_key=True),
        sa.Column('ror_id', sa.String(9), primary_key=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('country_code', sa.String(2)),
        sa.Column('search_text', sa.Text(), nullable=False),
        sa.Column('record_sha256', sa.String(64), nullable=False),
        sa.Column('source_ordinal', sa.Integer(), nullable=False),
        sa.Column('match_status', sa.String(40), nullable=False),
        sa.Column('data', postgresql.JSONB(), nullable=False),
        sa.Column('reconciliation', postgresql.JSONB(), nullable=False))
    op.create_index('ix_directory_country_name', 'directory_institutions', ['release_id', 'country_code', 'name'])
    op.create_index('ix_directory_match_status', 'directory_institutions', ['release_id', 'match_status'])


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT EXISTS (SELECT 1 FROM directory_releases)')):
        raise RuntimeError('Refusing to drop populated directory history.')
    op.drop_table('directory_institutions')
    op.drop_table('directory_releases')
