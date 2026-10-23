from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.models import SourceDocument


def test_freshness_columns_are_deferred_for_pre_migration_reads():
    sql = str(select(SourceDocument).compile(dialect=postgresql.dialect()))

    for column in ("source_published_at", "academic_period", "last_checked_at",
                   "last_content_changed_at"):
        assert column not in sql
