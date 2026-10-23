"""Add one grouped reviewer state per canonical institution.

Revision ID: e5a17c9b4d20
Revises: c7f1a906d2b3
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e5a17c9b4d20"
down_revision = "c7f1a906d2b3"
branch_labels = None
depends_on = None


AUTHORITATIVE_NAMESPACES = (
    "ror", "ror_grid", "ror_isni", "ror_wikidata", "ror_ringgold",
    "ipeds_unitid", "uai", "grid", "isni", "wikidata",
)


def upgrade() -> None:
    op.create_table(
        "institution_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("university_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="pending", nullable=False),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'deferred', 'needs_evidence')",
            name="ck_institution_reviews_status",
        ),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["university_id"], ["universities.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("university_id", name="uq_institution_reviews_university"),
    )
    op.create_index("ix_institution_reviews_status", "institution_reviews", ["status", "created_at"])

    op.create_table(
        "institution_review_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("review_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("before_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("after_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "action IN ('approve', 'reject', 'defer', 'needs_evidence')",
            name="ck_institution_review_events_action",
        ),
        sa.CheckConstraint("length(btrim(reason)) > 0", name="ck_institution_review_events_reason"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["review_id"], ["institution_reviews.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_institution_review_events_review", "institution_review_events", ["review_id", "created_at"]
    )

    # Existing real records receive pending review. A valid source identifier is
    # evidence for identity resolution, not a human institution approval.
    op.execute("""
        INSERT INTO institution_reviews (id, university_id, status)
        SELECT gen_random_uuid(), u.id, 'pending'
        FROM universities u
        WHERE COALESCE(u.external_identifiers->>'demo_fixture', 'false') <> 'true'
    """)

    # Auxiliary registry codes (for example state FIPS and institution-system IDs)
    # are retained but must not be labelled accepted identity claims.
    namespaces = ", ".join("'" + value + "'" for value in AUTHORITATIVE_NAMESPACES)
    op.execute(f"""
        UPDATE institution_identifiers
        SET claim_status = 'pending_review'
        WHERE claim_status = 'accepted' AND namespace NOT IN ({namespaces})
    """)

    op.execute("""
        CREATE FUNCTION reject_institution_review_event_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'institution review events are append-only';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER institution_review_events_immutable
        BEFORE UPDATE OR DELETE ON institution_review_events
        FOR EACH ROW EXECUTE FUNCTION reject_institution_review_event_mutation()
    """)


def downgrade() -> None:
    # Status reclassification is a conservative correction, retained on downgrade;
    # no identifier claim or existing review decision is removed.
    op.execute("DROP TRIGGER institution_review_events_immutable ON institution_review_events")
    op.execute("DROP FUNCTION reject_institution_review_event_mutation()")
    op.drop_index("ix_institution_review_events_review", table_name="institution_review_events")
    op.drop_table("institution_review_events")
    op.drop_index("ix_institution_reviews_status", table_name="institution_reviews")
    op.drop_table("institution_reviews")
