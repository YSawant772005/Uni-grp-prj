"""Operator CLI for the university data ingestion engine.

    python -m app.ingestion.cli sources
    python -m app.ingestion.cli run ror --dry-run
    python -m app.ingestion.cli run-all
    python -m app.ingestion.cli due --enqueue
    python -m app.ingestion.cli verify
"""
from __future__ import annotations

import argparse
import json
import logging
import sys

from sqlalchemy import func, or_, select

from app.db.session import SessionLocal
from app.ingestion import run_source
from app.ingestion.pipeline import RunOptions, enqueue_due_refreshes, run_all
from app.ingestion.registry import all_specs
from app.models import (
    FactEvidence,
    FactRecord,
    FactVersion,
    IngestionJob,
    Program,
    Source,
    SourceDocument,
    University,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")


def _print(payload) -> None:
    print(json.dumps(payload, indent=2, default=str))


def _is_ingested_institution():
    """Return the JSON identifier predicate used for real source-backed institutions."""
    return or_(
        University.external_identifiers["ror"].astext.is_not(None),
        University.external_identifiers["ipeds_unitid"].astext.is_not(None),
        University.external_identifiers["uai"].astext.is_not(None),
        University.external_identifiers["rio_provider_id"].astext.is_not(None),
    )


def cmd_sources(args) -> int:
    rows = []
    db = SessionLocal()
    try:
        for key, spec in sorted(all_specs().items()):
            row = db.scalar(select(Source).where(
                Source.metadata_json["adapter_key"].astext == key))
            rows.append({
                "source_key": key, "name": spec.name, "type": spec.source_type,
                "authority_tier": spec.authority_tier, "policy": spec.allowed_use_policy,
                "country_scope": spec.country_scope, "refresh_interval_hours":
                    spec.refresh_interval_hours,
                "registry_enabled": spec.enabled,
                "integration_status": spec.integration_status,
                "supported_data": list(spec.supported_data),
                "db_row": None if row is None else {
                    "id": str(row.id), "enabled": row.enabled,
                    "health": (row.metadata_json or {}).get("health"),
                },
            })
    finally:
        db.close()
    _print(rows)
    return 0


def cmd_set_enabled(args) -> int:
    """Operator override of a source's enabled state (registry + database)."""
    db = SessionLocal()
    try:
        source = db.scalar(select(Source).where(
            Source.metadata_json["adapter_key"].astext == args.source_key))
        if source is None:
            print(f"source {args.source_key!r} is not registered yet; run it once first",
                  file=sys.stderr)
            return 2
        source.enabled = args.enabled
        db.commit()
        _print({"source_key": args.source_key, "enabled": source.enabled})
    finally:
        db.close()
    return 0


def cmd_run(args) -> int:
    options = RunOptions(dry_run=args.dry_run, max_records=args.limit,
                         max_pages=args.max_pages, countries=args.country,
                         offline=args.offline, record_all_items=args.record_all_items,
                         query=args.query)
    summary = run_source(args.source_key, options)
    _print(summary.as_dict())
    return 1 if summary.status == "failed" else 0


def cmd_run_all(args) -> int:
    options = RunOptions(dry_run=args.dry_run, max_records=args.limit,
                         countries=args.country, offline=args.offline)
    summaries = [s.as_dict() for s in run_all(options)]
    _print(summaries)
    return 0 if all(s["status"] in ("succeeded", "dry_run") for s in summaries) else 1


def cmd_due(args) -> int:
    db = SessionLocal()
    try:
        queued = enqueue_due_refreshes(db)
        if args.enqueue:
            db.commit()
        _print({"due": len(queued), "queued": [str(j.id) for j in queued],
                "enqueued": bool(args.enqueue)})
    finally:
        db.close()
    return 0


def cmd_verify(args) -> int:
    """Query PostgreSQL directly and report what is actually persisted."""
    db = SessionLocal()
    try:
        def count(model, *where):
            return db.scalar(select(func.count()).select_from(model).where(*where)) or 0

        is_ror = University.external_identifiers["ror"].astext.is_not(None)
        is_ipeds = University.external_identifiers["ipeds_unitid"].astext.is_not(None)
        is_real = _is_ingested_institution()
        ingested_ids = select(University.id).where(is_real)

        by_status = db.execute(
            select(FactRecord.current_status, func.count())
            .where(FactRecord.entity_type == "university",
                   FactRecord.entity_id.in_(ingested_ids))
            .group_by(FactRecord.current_status)).all()
        by_key = db.execute(
            select(FactRecord.fact_key, func.count())
            .where(FactRecord.entity_type == "university",
                   FactRecord.entity_id.in_(ingested_ids))
            .group_by(FactRecord.fact_key).order_by(func.count().desc())).all()
        per_source = db.execute(
            select(Source.name, func.count(func.distinct(FactRecord.id)))
            .join(SourceDocument, SourceDocument.source_id == Source.id)
            .join(FactEvidence, FactEvidence.source_document_id == SourceDocument.id)
            .join(FactVersion, FactVersion.id == FactEvidence.fact_version_id)
            .join(FactRecord, FactRecord.id == FactVersion.fact_record_id)
            .group_by(Source.name)).all()
        countries = db.execute(
            select(University.country_code, func.count())
            .where(is_real).group_by(University.country_code)
            .order_by(func.count().desc())).all()
        jobs = db.execute(
            select(IngestionJob.source_id, IngestionJob.status, func.count())
            .group_by(IngestionJob.source_id, IngestionJob.status)).all()
        last_success = db.scalar(
            select(func.max(IngestionJob.finished_at)).where(IngestionJob.status == "succeeded"))
        report = {
            "registered_connectors": len(all_specs()),
            "source_rows_in_database": count(Source),
            "institutions_total": count(University),
            "institutions_from_ingestion": (
                db.scalar(select(func.count()).select_from(University).where(is_real)) or 0),
            "institutions_synthetic_demo": count(University) - (
                db.scalar(select(func.count()).select_from(University).where(is_real)) or 0),
            "programs_total": count(Program),
            "fact_records": count(FactRecord),
            "fact_versions": count(FactVersion),
            "fact_evidence": count(FactEvidence),
            "source_documents": count(SourceDocument),
            "ingestion_jobs": count(IngestionJob),
            "ingested_facts_by_status": [{"status": s, "count": n} for s, n in by_status],
            "ingested_facts_by_key": [{"fact_key": k, "count": n} for k, n in by_key],
            "facts_per_source": [{"source": name, "facts": n} for name, n in per_source],
            "ingested_countries_top_20": [{"country": c, "count": n} for c, n in countries[:20]],
            "distinct_countries": len(countries),
            "jobs_by_source_status": [{"source_id": str(sid), "status": st, "count": n}
                                      for sid, st, n in jobs],
            "last_successful_ingestion": last_success,
        }
        _print(report)
    finally:
        db.close()
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="app.ingestion.cli",
                                     description="University data ingestion engine")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("sources", help="list registered connectors and their status").set_defaults(
        fn=cmd_sources)

    p = sub.add_parser("enable", help="enable a registered source")
    p.add_argument("source_key")
    p.set_defaults(fn=cmd_set_enabled, enabled=True)
    p = sub.add_parser("disable", help="disable a registered source")
    p.add_argument("source_key")
    p.set_defaults(fn=cmd_set_enabled, enabled=False)

    p = sub.add_parser("run", help="run one connector")
    p.add_argument("source_key")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit", type=int, default=None, help="max records (smoke test)")
    p.add_argument("--max-pages", type=int, default=None)
    p.add_argument("--country", action="append", dest="country")
    p.add_argument("--offline", action="store_true", help="use cached downloads only")
    p.add_argument("--record-all-items", action="store_true")
    p.add_argument("--query", help="exact source query supported by selected adapter")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("run-all", help="run every enabled connector")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--country", action="append", dest="country")
    p.add_argument("--offline", action="store_true")
    p.set_defaults(fn=cmd_run_all)

    p = sub.add_parser("due", help="list/queue refreshes whose interval has elapsed")
    p.add_argument("--enqueue", action="store_true")
    p.set_defaults(fn=cmd_due)

    sub.add_parser("verify", help="query PostgreSQL and report persisted rows").set_defaults(
        fn=cmd_verify)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
