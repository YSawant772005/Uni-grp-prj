"""Persist selected named Master's award, separate from specialization.

Revision ID: c41de67a920f
Revises: b7f4d2c9a1e3
"""
from alembic import op
import sqlalchemy as sa

revision = "c41de67a920f"
down_revision = "b7f4d2c9a1e3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("student_profiles", sa.Column("desired_degree_title", sa.String(length=200), nullable=True))


def downgrade():
    op.drop_column("student_profiles", "desired_degree_title")
