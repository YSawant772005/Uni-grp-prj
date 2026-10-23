"""Enforce authoritative identifier uniqueness across institution scopes.

Revision ID: b4e981c72a63
Revises: a3d2f7c98e41
"""
from alembic import op
import sqlalchemy as sa

revision = "b4e981c72a63"
down_revision = "a3d2f7c98e41"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # If earlier scope rules allowed two accepted claims for one authoritative
    # identifier, retain both and quarantine them rather than selecting a winner.
    op.execute(sa.text("""
        WITH duplicate_keys AS (
            SELECT namespace, normalized_value, scope
              FROM institution_identifiers
             WHERE claim_status = 'accepted'
               AND namespace IN ('ror', 'ror_grid', 'ror_isni', 'ror_wikidata', 'ror_ringgold',
                                 'ipeds_unitid', 'grid', 'isni', 'wikidata')
             GROUP BY namespace, normalized_value, scope
            HAVING count(DISTINCT university_id) > 1
        )
        UPDATE institution_identifiers AS claim
           SET claim_status = 'conflicted'
          FROM duplicate_keys AS duplicate
         WHERE claim.namespace = duplicate.namespace
           AND claim.normalized_value = duplicate.normalized_value
           AND claim.scope = duplicate.scope
           AND claim.claim_status = 'accepted'
    """))
    op.drop_index("uq_institution_identifiers_authoritative", table_name="institution_identifiers")
    op.create_index(
        "uq_institution_identifiers_authoritative", "institution_identifiers",
        ["namespace", "normalized_value", "scope"], unique=True,
        postgresql_where=sa.text(
            "claim_status = 'accepted' AND namespace IN ('ror', 'ror_grid', 'ror_isni', "
            "'ror_wikidata', 'ror_ringgold', 'ipeds_unitid', 'grid', 'isni', 'wikidata')"),
    )


def downgrade() -> None:
    op.drop_index("uq_institution_identifiers_authoritative", table_name="institution_identifiers")
    op.create_index(
        "uq_institution_identifiers_authoritative", "institution_identifiers",
        ["namespace", "normalized_value", "scope"], unique=True,
        postgresql_where=sa.text(
            "claim_status = 'accepted' AND scope <> 'campus' AND "
            "namespace IN ('ror', 'ror_grid', 'ror_isni', 'ror_wikidata', 'ror_ringgold', "
            "'ipeds_unitid', 'grid', 'isni', 'wikidata')"),
    )
