"""Prevent mutation of institution identity review audit evidence.

Revision ID: c7f1a906d2b3
Revises: b4e981c72a63
"""
from alembic import op

revision = "c7f1a906d2b3"
down_revision = "b4e981c72a63"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION reject_identity_review_event_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'institution identity review events are append-only';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER institution_identity_review_events_immutable
        BEFORE UPDATE OR DELETE ON institution_identity_review_events
        FOR EACH ROW EXECUTE FUNCTION reject_identity_review_event_mutation()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER institution_identity_review_events_immutable "
               "ON institution_identity_review_events")
    op.execute("DROP FUNCTION reject_identity_review_event_mutation()")
