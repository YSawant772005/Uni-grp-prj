"""Persist source-specific programme identities.

Revision ID: a3d2f7c98e41
Revises: 93cb147f6e20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a3d2f7c98e41"
down_revision = "93cb147f6e20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A title/slug is descriptive, not a reliable identity. Multiple distinct
    # programmes may share it, including at different campuses.
    op.drop_constraint("uq_programs_identity", "programs", type_="unique")
    op.create_table(
        "program_identifiers",
        sa.Column("program_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_document_id", sa.Uuid(), nullable=False),
        sa.Column("source_key", sa.String(80), nullable=False),
        sa.Column("external_key", sa.String(250), nullable=False),
        sa.Column("normalized_external_key", sa.String(250), nullable=False),
        sa.Column("claim_status", sa.String(24), server_default="accepted", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_key", "normalized_external_key", "program_id",
                            name="uq_program_identifier_claim"),
        sa.CheckConstraint("claim_status IN ('accepted', 'pending_review', 'conflicted', 'rejected')",
                           name="ck_program_identifiers_status"),
    )
    op.create_index("ix_program_identifiers_program", "program_identifiers", ["program_id"])
    op.create_index("uq_program_identifiers_source_key", "program_identifiers",
                    ["source_key", "normalized_external_key"], unique=True,
                    postgresql_where=sa.text("claim_status = 'accepted'"))


def downgrade() -> None:
    op.drop_index("uq_program_identifiers_source_key", table_name="program_identifiers")
    op.drop_index("ix_program_identifiers_program", table_name="program_identifiers")
    op.drop_table("program_identifiers")
    # This restoration can fail if distinct programmes have equal slug/degree at
    # one university; never delete or collapse them to force a downgrade.
    op.create_unique_constraint("uq_programs_identity", "programs",
                                ["university_id", "slug", "degree_level"])
