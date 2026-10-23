"""Add scope-aware identity claims and human identity review history.

Revision ID: 93cb147f6e20
Revises: 6af8c2d94b10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "93cb147f6e20"
down_revision = "6af8c2d94b10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("institution_identifiers", sa.Column("campus_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_institution_identifiers_campus_id_campuses", "institution_identifiers",
                          "campuses", ["campus_id"], ["id"], ondelete="RESTRICT")
    op.drop_constraint("ck_institution_identifiers_scope", "institution_identifiers", type_="check")
    op.create_check_constraint(
        "ck_institution_identifiers_scope", "institution_identifiers",
        "scope IN ('institution', 'campus', 'reporting_unit') AND "
        "((scope = 'campus' AND campus_id IS NOT NULL) OR "
        "(scope <> 'campus' AND campus_id IS NULL))")
    op.drop_constraint("uq_institution_identifier_claim", "institution_identifiers", type_="unique")
    op.create_unique_constraint("uq_institution_identifier_claim", "institution_identifiers",
                                ["source_key", "namespace", "normalized_value", "scope", "university_id"])
    op.execute(sa.text("UPDATE institution_identifiers SET scope='reporting_unit' "
                       "WHERE namespace='ipeds_unitid' AND scope='institution'"))
    op.drop_index("uq_institution_identifiers_authoritative", table_name="institution_identifiers")
    op.create_index(
        "uq_institution_identifiers_authoritative", "institution_identifiers",
        ["namespace", "normalized_value", "scope"], unique=True,
        postgresql_where=sa.text(
            "claim_status = 'accepted' AND scope <> 'campus' AND "
            "namespace IN ('ror', 'ror_grid', 'ror_isni', 'ror_wikidata', 'ror_ringgold', "
            "'ipeds_unitid', 'grid', 'isni', 'wikidata')"),
    )

    op.create_table(
        "institution_identity_reviews",
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_document_id", sa.Uuid(), nullable=False),
        sa.Column("external_key", sa.String(200), nullable=False),
        sa.Column("candidate_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("suggested_university_id", sa.Uuid(), nullable=True),
        sa.Column("resolved_university_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(24), server_default="pending", nullable=False),
        sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected', 'deferred')",
                           name="ck_institution_identity_reviews_status"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["suggested_university_id"], ["universities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resolved_university_id"], ["universities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "external_key", name="uq_institution_identity_review_source_key"),
    )
    op.create_index("ix_institution_identity_reviews_status", "institution_identity_reviews",
                    ["status", "created_at"])
    op.create_table(
        "institution_identity_review_events",
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("before_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("after_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("action IN ('approve_link', 'reject', 'defer')",
                           name="ck_institution_identity_review_events_action"),
        sa.CheckConstraint("length(btrim(reason)) > 0", name="ck_institution_identity_review_events_reason"),
        sa.ForeignKeyConstraint(["review_id"], ["institution_identity_reviews.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_institution_identity_review_events_review",
                    "institution_identity_review_events", ["review_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_institution_identity_review_events_review",
                  table_name="institution_identity_review_events")
    op.drop_table("institution_identity_review_events")
    op.drop_index("ix_institution_identity_reviews_status", table_name="institution_identity_reviews")
    op.drop_table("institution_identity_reviews")
    op.drop_index("uq_institution_identifiers_authoritative", table_name="institution_identifiers")
    op.execute(sa.text("UPDATE institution_identifiers SET scope='institution' "
                       "WHERE namespace='ipeds_unitid' AND scope='reporting_unit'"))
    op.create_index(
        "uq_institution_identifiers_authoritative", "institution_identifiers",
        ["namespace", "normalized_value"], unique=True,
        postgresql_where=sa.text(
            "claim_status = 'accepted' AND scope = 'institution' AND "
            "namespace IN ('ror', 'ror_grid', 'ror_isni', 'ror_wikidata', 'ror_ringgold', "
            "'ipeds_unitid', 'grid', 'isni', 'wikidata')"),
    )
    op.drop_constraint("uq_institution_identifier_claim", "institution_identifiers", type_="unique")
    op.create_unique_constraint("uq_institution_identifier_claim", "institution_identifiers",
                                ["source_key", "namespace", "normalized_value", "university_id"])
    op.drop_constraint("ck_institution_identifiers_scope", "institution_identifiers", type_="check")
    op.create_check_constraint("ck_institution_identifiers_scope", "institution_identifiers",
                               "scope IN ('institution', 'campus', 'reporting_unit')")
    op.drop_constraint("fk_institution_identifiers_campus_id_campuses", "institution_identifiers",
                       type_="foreignkey")
    op.drop_column("institution_identifiers", "campus_id")
