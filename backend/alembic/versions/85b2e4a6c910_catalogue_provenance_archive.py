"""Independent catalogue archives and retained, detached historical reviews.

Revision ID: 85b2e4a6c910
Revises: 7a3d9f2c1e60
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "85b2e4a6c910"
down_revision = "7a3d9f2c1e60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "catalogue_reset_operations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("operator", sa.String(200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("original_revision", sa.String(32), nullable=False),
        sa.Column("backup_path", sa.Text(), nullable=False),
        sa.Column("backup_sha256", sa.String(64), nullable=False),
        sa.Column("manifest", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("length(backup_sha256) = 64", name="ck_catalogue_reset_backup_hash"),
    )
    op.create_table(
        "catalogue_archive_records",
        sa.Column("operation_id", sa.Uuid(), sa.ForeignKey("catalogue_reset_operations.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("table_name", sa.String(80), primary_key=True),
        sa.Column("record_key", sa.String(250), primary_key=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("row_sha256", sa.String(64), nullable=False),
        sa.CheckConstraint("length(row_sha256) = 64", name="ck_catalogue_archive_row_hash"),
    )
    for table in ("institution_reviews", "institution_identity_reviews"):
        op.add_column(table, sa.Column("archived_operation_id", sa.Uuid(), nullable=True, server_default=sa.text("NULL")))
        op.create_foreign_key(f"{table}_archived_operation_id_fkey", table, "catalogue_reset_operations",
                              ["archived_operation_id"], ["id"], ondelete="RESTRICT")
    op.alter_column("institution_reviews", "university_id", nullable=True)
    op.create_check_constraint("ck_institution_review_active_or_archived", "institution_reviews",
        "(university_id IS NOT NULL AND archived_operation_id IS NULL) OR "
        "(university_id IS NULL AND archived_operation_id IS NOT NULL)")
    op.create_check_constraint("ck_identity_review_archived_links", "institution_identity_reviews",
        "archived_operation_id IS NULL OR (suggested_university_id IS NULL AND resolved_university_id IS NULL)")
    op.drop_constraint("uq_institution_identity_review_source_key", "institution_identity_reviews", type_="unique")
    op.create_index("uq_institution_identity_review_active_source_key", "institution_identity_reviews",
                    ["source_id", "external_key"], unique=True,
                    postgresql_where=sa.text("archived_operation_id IS NULL"))
    op.execute("""
        CREATE FUNCTION reject_catalogue_archive_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
            RAISE EXCEPTION 'catalogue archives are append-only';
        END; $$
    """)
    for table in ("catalogue_reset_operations", "catalogue_archive_records"):
        op.execute(f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
                   "FOR EACH ROW EXECUTE FUNCTION reject_catalogue_archive_mutation()")


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM catalogue_reset_operations)")):
        raise RuntimeError("Refusing downgrade: catalogue archive history exists. Restore an independently verified backup instead.")
    op.drop_index("uq_institution_identity_review_active_source_key", table_name="institution_identity_reviews")
    op.create_unique_constraint("uq_institution_identity_review_source_key", "institution_identity_reviews", ["source_id", "external_key"])
    op.drop_constraint("ck_identity_review_archived_links", "institution_identity_reviews", type_="check")
    op.drop_constraint("ck_institution_review_active_or_archived", "institution_reviews", type_="check")
    op.alter_column("institution_reviews", "university_id", nullable=False)
    for table in ("institution_reviews", "institution_identity_reviews"):
        op.drop_constraint(f"{table}_archived_operation_id_fkey", table, type_="foreignkey")
        op.drop_column(table, "archived_operation_id")
    op.drop_table("catalogue_archive_records")
    op.drop_table("catalogue_reset_operations")
    op.execute("DROP FUNCTION reject_catalogue_archive_mutation()")
