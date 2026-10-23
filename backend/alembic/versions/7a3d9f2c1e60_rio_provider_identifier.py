"""Enforce the source-scoped RIO education-provider identifier.

Revision ID: 7a3d9f2c1e60
Revises: f6b2a14d8c30
"""
from alembic import op
import sqlalchemy as sa


revision = "7a3d9f2c1e60"
down_revision = "f6b2a14d8c30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_institution_identifiers_rio_provider",
        "institution_identifiers",
        ["source_key", "namespace", "normalized_value", "scope"],
        unique=True,
        postgresql_where=sa.text(
            "claim_status = 'accepted' AND namespace = 'rio_provider_id'"),
    )


def downgrade() -> None:
    op.drop_index("uq_institution_identifiers_rio_provider",
                  table_name="institution_identifiers")
