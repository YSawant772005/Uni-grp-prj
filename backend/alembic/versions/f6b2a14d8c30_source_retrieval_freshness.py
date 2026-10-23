"""Track source document periods, retrieval attempts, and content changes.

Revision ID: f6b2a14d8c30
Revises: e5a17c9b4d20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f6b2a14d8c30"
down_revision = "e5a17c9b4d20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("source_documents", sa.Column("source_published_at", sa.Date(), nullable=True))
    op.add_column("source_documents", sa.Column("academic_period", sa.String(32), nullable=True))
    op.add_column("source_documents", sa.Column(
        "last_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("source_documents", sa.Column(
        "last_content_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE source_documents SET last_checked_at = retrieved_at, "
               "last_content_changed_at = retrieved_at")
    op.alter_column("source_documents", "last_checked_at", nullable=False,
                    server_default=sa.func.now())
    op.alter_column("source_documents", "last_content_changed_at", nullable=False,
                    server_default=sa.func.now())

    op.create_table(
        "source_document_retrievals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("http_status", sa.SmallInteger(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("etag", sa.String(200), nullable=True),
        sa.Column("last_modified", sa.String(200), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.CheckConstraint("outcome IN ('fetched', 'not_modified', 'failed')",
                           name="ck_source_document_retrievals_outcome"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_source_document_retrievals_source_time",
                    "source_document_retrievals", ["source_id", "attempted_at"])
    op.create_index("ix_source_document_retrievals_document_time",
                    "source_document_retrievals", ["source_document_id", "attempted_at"])
    op.execute("""
        CREATE FUNCTION reject_source_document_retrieval_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'source document retrievals are append-only';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER source_document_retrievals_immutable
        BEFORE UPDATE OR DELETE ON source_document_retrievals
        FOR EACH ROW EXECUTE FUNCTION reject_source_document_retrieval_mutation()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER source_document_retrievals_immutable ON source_document_retrievals")
    op.execute("DROP FUNCTION reject_source_document_retrieval_mutation()")
    op.drop_index("ix_source_document_retrievals_document_time", table_name="source_document_retrievals")
    op.drop_index("ix_source_document_retrievals_source_time", table_name="source_document_retrievals")
    op.drop_table("source_document_retrievals")
    op.drop_column("source_documents", "last_content_changed_at")
    op.drop_column("source_documents", "last_checked_at")
    op.drop_column("source_documents", "academic_period")
    op.drop_column("source_documents", "source_published_at")
