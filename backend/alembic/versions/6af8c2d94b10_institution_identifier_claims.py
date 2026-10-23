"""Add source-attributed institution identifier claims.

Revision ID: 6af8c2d94b10
Revises: d91f2ab34c05
"""
from alembic import op
import sqlalchemy as sa

revision = "6af8c2d94b10"
down_revision = ("d91f2ab34c05", "b7f4d2c9a1e3")
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "institution_identifiers",
        sa.Column("university_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("source_document_id", sa.Uuid(), nullable=True),
        sa.Column("source_key", sa.String(80), nullable=False),
        sa.Column("namespace", sa.String(80), nullable=False),
        sa.Column("identifier_value", sa.String(250), nullable=False),
        sa.Column("normalized_value", sa.String(250), nullable=False),
        sa.Column("scope", sa.String(24), server_default="institution", nullable=False),
        sa.Column("claim_status", sa.String(24), server_default="accepted", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["university_id"], ["universities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_key", "namespace", "normalized_value", "university_id",
                            name="uq_institution_identifier_claim"),
        sa.CheckConstraint("scope IN ('institution', 'campus', 'reporting_unit')",
                           name="ck_institution_identifiers_scope"),
        sa.CheckConstraint("claim_status IN ('accepted', 'pending_review', 'conflicted', 'rejected')",
                           name="ck_institution_identifiers_status"),
    )
    op.create_index("ix_institution_identifiers_lookup", "institution_identifiers",
                    ["namespace", "normalized_value"])
    op.create_index("ix_institution_identifiers_university", "institution_identifiers",
                    ["university_id"])

    # Keep every legacy claim. Duplicate authoritative values are retained as
    # conflicted claims; no winner is selected during migration.
    op.execute(sa.text("""
        WITH claims AS (
            SELECT u.id AS university_id, item.key AS namespace,
                   btrim(item.value) AS identifier_value,
                   lower(btrim(item.value)) AS normalized_value,
                   count(*) OVER (PARTITION BY item.key, lower(btrim(item.value))) AS claim_count
              FROM universities AS u
              CROSS JOIN LATERAL jsonb_each_text(COALESCE(u.external_identifiers, '{}'::jsonb)) AS item
             WHERE item.key <> 'demo_fixture'
               AND btrim(item.value) <> ''
        )
        INSERT INTO institution_identifiers
            (id, university_id, source_key, namespace, identifier_value,
             normalized_value, scope, claim_status)
        SELECT gen_random_uuid(), university_id, 'legacy_jsonb', namespace,
               identifier_value, normalized_value, 'institution',
               CASE WHEN claim_count > 1 THEN 'conflicted' ELSE 'accepted' END
          FROM claims
        ON CONFLICT (source_key, namespace, normalized_value, university_id) DO NOTHING
    """))
    op.create_index(
        "uq_institution_identifiers_authoritative",
        "institution_identifiers", ["namespace", "normalized_value"], unique=True,
        postgresql_where=sa.text(
            "claim_status = 'accepted' AND scope = 'institution' AND "
            "namespace IN ('ror', 'ror_grid', 'ror_isni', 'ror_wikidata', 'ror_ringgold', "
            "'ipeds_unitid', 'grid', 'isni', 'wikidata')"),
    )


def downgrade() -> None:
    op.drop_index("uq_institution_identifiers_authoritative", table_name="institution_identifiers")
    op.drop_index("ix_institution_identifiers_university", table_name="institution_identifiers")
    op.drop_index("ix_institution_identifiers_lookup", table_name="institution_identifiers")
    op.drop_table("institution_identifiers")
