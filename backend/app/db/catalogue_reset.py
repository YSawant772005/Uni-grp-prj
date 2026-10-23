"""Plan and execute an explicitly confirmed catalogue archive/reset transaction.

No server startup or HTTP endpoint calls this module. Development execution is an
operator action after exact approval; recovery/test targets require their markers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from app.db.safety import verify_development_target, verify_recovery_target, verify_test_target

REVISION = "85b2e4a6c910"
SUPPORTED_REVISIONS = {REVISION, "9c24a7e6d180"}
ARCHIVE_TABLES = {"catalogue_reset_operations", "catalogue_archive_records"}
DELETE_TABLES = (
    "fact_review_events", "fact_evidence", "fact_versions", "fact_records",
    "scholarship_program_links", "program_outcome_evidence", "program_fees",
    "admission_requirements", "program_intakes", "program_identifiers",
    "institution_identifiers", "programs", "campuses", "universities",
)
PROVENANCE_TABLES = (
    "sources", "source_documents", "source_document_retrievals", "ingestion_jobs",
    "ingestion_job_items", "audit_events", "institution_reviews",
    "institution_review_events", "institution_identity_reviews", "institution_identity_review_events",
)
USER_PROGRAM_DEPENDENCIES = {
    "saved_programs": "program_id", "comparison_items": "program_id",
    "recommendation_items": "program_id", "cost_scenarios": "program_id",
    "roi_scenarios": "program_id",
}


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def _rows(connection, table: str, where: str = "TRUE") -> list[dict]:
    # Table/where expressions are code constants or inspected PostgreSQL names.
    return list(connection.scalars(text(
        f'SELECT to_jsonb(t) FROM "{table}" t WHERE {where} ORDER BY to_jsonb(t)::text')))


def _scope(connection) -> dict[str, str]:
    program = "SELECT id FROM programs"
    university = "SELECT id FROM universities"
    outcome = "SELECT id FROM program_outcome_evidence WHERE program_id IS NOT NULL OR university_id IS NOT NULL"
    entities = {
        "program": program, "university": university, "outcome": outcome,
        "campus": "SELECT id FROM campuses", "fee": "SELECT id FROM program_fees",
        "requirement": "SELECT id FROM admission_requirements", "intake": "SELECT id FROM program_intakes",
    }
    fact = " OR ".join(f"(entity_type='{kind}' AND entity_id IN ({ids}))" for kind, ids in entities.items())
    fact_ids = f"SELECT id FROM fact_records WHERE {fact}"
    versions = f"SELECT id FROM fact_versions WHERE fact_record_id IN ({fact_ids})"
    return {
        "fact_records": fact,
        "fact_versions": f"fact_record_id IN ({fact_ids})",
        "fact_evidence": f"fact_version_id IN ({versions})",
        "fact_review_events": f"fact_record_id IN ({fact_ids})",
        "program_outcome_evidence": "program_id IS NOT NULL OR university_id IS NOT NULL",
    }


def snapshot(connection) -> dict:
    tables = sorted(set(inspect(connection).get_table_names(schema="public")) - ARCHIVE_TABLES - {"alembic_version"})
    # Nullable archival metadata is additive; the original backup and the
    # migrated pre-reset rows must still have comparable content fingerprints.
    def original_columns(rows):
        return [{k: v for k, v in row.items() if k != "archived_operation_id" or v is not None}
                for row in rows]

    return {table: {"count": len(rows), "sha256": digest(original_columns(rows))}
            for table in tables if (rows := _rows(connection, table)) is not None}


def plan_reset(connection, *, operation_id: uuid.UUID, backup_path: str,
               backup_sha256: str, operator: str, reason: str) -> dict:
    if not operator.strip() or not reason.strip() or len(operator) > 200:
        raise RuntimeError("A named operator and reset justification are required.")
    revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
    if revision not in SUPPORTED_REVISIONS:
        raise RuntimeError(f"Reset requires a rehearsed archive-compatible revision: {sorted(SUPPORTED_REVISIONS)}.")
    if connection.scalar(text("SELECT count(*) FROM ingestion_jobs WHERE status IN ('queued','running')")):
        raise RuntimeError("Refusing reset while ingestion jobs are queued or running.")
    for table, column in USER_PROGRAM_DEPENDENCIES.items():
        if connection.scalar(text(f'SELECT EXISTS (SELECT 1 FROM "{table}" WHERE {column} IS NOT NULL)')):
            raise RuntimeError(f"Refusing reset: {table} contains protected student programme associations.")
    scope = _scope(connection)
    catalogue_ids = " UNION ".join(f"SELECT id FROM {table}" for table in
                                   ("universities", "programs", "campuses", "program_fees", "admission_requirements", "program_intakes"))
    # Refuse unsupported polymorphic links instead of leaving active orphan facts.
    if connection.scalar(text(f"SELECT EXISTS (SELECT 1 FROM fact_records WHERE entity_id IN ({catalogue_ids}) AND NOT ({scope['fact_records']}))")):
        raise RuntimeError("Refusing reset: unrecognised catalogue fact association.")
    fact_ids = "SELECT id FROM fact_records WHERE " + scope["fact_records"]
    for table, column in (("scholarships", "fact_id"), ("funding_opportunities", "fact_id"),
                          ("living_cost_facts", "fact_id"), ("official_rule_resources", "fact_id"),
                          ("scholarship_eligibility_rules", "source_fact_id")):
        if connection.scalar(text(f'SELECT EXISTS (SELECT 1 FROM "{table}" WHERE {column} IN ({fact_ids}))')):
            raise RuntimeError(f"Refusing reset: protected {table} references catalogue facts.")
    before = snapshot(connection)
    delete_counts = {table: len(_rows(connection, table, scope.get(table, "TRUE"))) for table in DELETE_TABLES}
    protected_rows = {table: {"count": len(rows), "sha256": digest(rows)}
                      for table, where in scope.items()
                      if (rows := _rows(connection, table, f"NOT ({where})")) is not None}
    plan = {"format": 1, "operation_id": str(operation_id), "revision": revision,
            "backup_path": backup_path, "backup_sha256": backup_sha256,
            "operator": operator.strip(), "reason": reason.strip(),
            "before": before, "delete_counts": delete_counts, "protected_rows": protected_rows,
            "preserve_live": list(PROVENANCE_TABLES),
            "archive_tables": sorted(set(DELETE_TABLES) | set(PROVENANCE_TABLES))}
    return {**plan, "confirmation_sha256": digest(plan)}


def execute_reset(connection, plan: dict, *, confirm: str) -> dict:
    """Caller supplies a transaction; every assertion failure rolls back everything."""
    if confirm != plan.get("confirmation_sha256") or confirm != digest({k: v for k, v in plan.items() if k != "confirmation_sha256"}):
        raise RuntimeError("Exact reset plan confirmation does not match.")
    connection.execute(text("SET LOCAL lock_timeout = '5s'"))
    connection.execute(text("SET LOCAL statement_timeout = '60s'"))
    connection.execute(text("SELECT pg_advisory_xact_lock(810932710)"))
    # Lock the inspected application tables in deterministic order: no concurrent
    # review, user edit or ingestion can race the plan comparison and archival.
    names = sorted(inspect(connection).get_table_names(schema="public"))
    connection.execute(text("LOCK TABLE " + ", ".join('"' + name + '"' for name in names) + " IN ACCESS EXCLUSIVE MODE"))
    operation_id = uuid.UUID(plan["operation_id"])
    existing = connection.scalar(text("SELECT manifest FROM catalogue_reset_operations WHERE id=:id"), {"id": operation_id})
    if existing is not None:
        if existing != plan:
            raise RuntimeError("Reset operation ID already belongs to another plan.")
        return {"operation_id": str(operation_id), "already_applied": True}
    current = plan_reset(connection, operation_id=operation_id, backup_path=plan["backup_path"],
                         backup_sha256=plan["backup_sha256"], operator=plan["operator"], reason=plan["reason"])
    if current != plan:
        raise RuntimeError("Database changed since preflight; generate and approve a new exact plan.")
    scope = _scope(connection)
    archives = {table: _rows(connection, table, scope.get(table, "TRUE")) for table in plan["archive_tables"]}
    connection.execute(text("""INSERT INTO catalogue_reset_operations
        (id,operator,reason,original_revision,backup_path,backup_sha256,manifest)
        VALUES (:id,:operator,:reason,:revision,:backup_path,:backup_sha256,CAST(:manifest AS jsonb))"""),
        {**{k: plan[k] for k in ("operator", "reason", "backup_path", "backup_sha256")},
         "id": operation_id, "revision": plan["revision"], "manifest": json.dumps(plan)})
    for table, rows in archives.items():
        values = [{"op": operation_id, "table": table, "key": str(row.get("id") or digest(row)),
                   "payload": json.dumps(row), "hash": digest(row)} for row in rows]
        if values:
            connection.execute(text("""INSERT INTO catalogue_archive_records
                (operation_id,table_name,record_key,payload,row_sha256)
                VALUES (:op,:table,:key,CAST(:payload AS jsonb),:hash)"""), values)
    # Verify every archive row, including the complete original review associations,
    # against the independent snapshot before changing a single active record.
    for table, rows in archives.items():
        archived = list(connection.scalars(text("SELECT payload FROM catalogue_archive_records WHERE operation_id=:op AND table_name=:table ORDER BY payload::text"), {"op": operation_id, "table": table}))
        if digest(archived) != digest(rows):
            raise RuntimeError(f"Archive verification failed for {table}.")
    connection.execute(text("UPDATE institution_reviews SET archived_operation_id=:op, university_id=NULL WHERE university_id IS NOT NULL"), {"op": operation_id})
    connection.execute(text("UPDATE institution_identity_reviews SET archived_operation_id=:op, suggested_university_id=NULL, resolved_university_id=NULL WHERE archived_operation_id IS NULL"), {"op": operation_id})
    # Materialise fact IDs because their entity subqueries disappear as child
    # rows are removed. Temp tables are local to this transaction and connection.
    connection.execute(text("CREATE TEMP TABLE reset_fact_ids ON COMMIT DROP AS SELECT id FROM fact_records WHERE " + scope["fact_records"]))
    connection.execute(text("UPDATE fact_records SET current_version_id=NULL WHERE id IN (SELECT id FROM reset_fact_ids)"))
    delete_scope = dict(scope)
    delete_scope.update({"fact_records": "id IN (SELECT id FROM reset_fact_ids)",
                         "fact_versions": "fact_record_id IN (SELECT id FROM reset_fact_ids)",
                         "fact_evidence": "fact_version_id IN (SELECT id FROM fact_versions WHERE fact_record_id IN (SELECT id FROM reset_fact_ids))",
                         "fact_review_events": "fact_record_id IN (SELECT id FROM reset_fact_ids)"})
    for table in DELETE_TABLES:
        result = connection.execute(text(f'DELETE FROM "{table}" WHERE {delete_scope.get(table, "TRUE")}'))
        if result.rowcount != plan["delete_counts"][table]:
            raise RuntimeError(f"Unexpected deletion count for {table}; rolling back.")
    after = snapshot(connection)
    mutable = set(DELETE_TABLES) | {"institution_reviews", "institution_identity_reviews", "ingestion_job_items"}
    for table in set(after) - mutable:
        if after[table] != plan["before"][table]:
            raise RuntimeError(f"Protected table {table} changed; rolling back.")
    if after["universities"]["count"] or after["programs"]["count"]:
        raise RuntimeError("Active catalogue is not empty; rolling back.")
    for table, expected in plan["protected_rows"].items():
        rows = _rows(connection, table)
        if {"count": len(rows), "sha256": digest(rows)} != expected:
            raise RuntimeError(f"Unrelated reference rows in {table} changed; rolling back.")
    return {"operation_id": str(operation_id), "already_applied": False,
            "archived_records": sum(map(len, archives.values())), "active_universities": 0, "active_programs": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("proof", "plan", "execute"))
    parser.add_argument("--target", required=True, choices=("test", "recovery", "development"))
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--operation-id", type=uuid.UUID)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--operator")
    parser.add_argument("--reason")
    parser.add_argument("--confirm")
    args = parser.parse_args()
    from app.core.config import settings
    checks = {"test": verify_test_target, "recovery": verify_recovery_target, "development": verify_development_target}
    checks[args.target](settings.database_url)
    engine = create_engine(settings.database_url)
    try:
        if args.action == "proof":
            if args.target != "recovery" or not args.backup:
                parser.error("proof requires a marked recovery target and --backup")
            backup = args.backup.resolve(strict=True)
            metadata = dict(line.split("=", 1) for line in Path(str(backup) + ".meta").read_text().splitlines())
            with engine.connect() as connection:
                connection.execute(text("SET TRANSACTION READ ONLY"))
                revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
                if metadata["alembic_revision"] != revision:
                    raise RuntimeError("Restore proof requires the original backup schema revision.")
                proof = {"backup_sha256": hashlib.sha256(backup.read_bytes()).hexdigest(),
                         "restored_revision": revision, "tables": snapshot(connection)}
            proof_path = Path(str(backup) + ".restore-proof.json")
            proof_path.write_text(json.dumps(proof, indent=2) + "\n")
            proof_path.chmod(0o600)
            print(json.dumps({"restore_proof": str(proof_path), "backup_sha256": proof["backup_sha256"]}))
        elif args.action == "plan":
            if not args.plan:
                parser.error("plan requires --plan")
            if not all((args.operation_id, args.backup, args.operator, args.reason)):
                parser.error("plan requires --operation-id, --backup, --operator and --reason")
            backup = args.backup.resolve(strict=True)
            backup_hash = hashlib.sha256(backup.read_bytes()).hexdigest()
            proof = json.loads(Path(str(backup) + ".restore-proof.json").read_text())
            if proof["backup_sha256"] != backup_hash:
                raise RuntimeError("Backup does not match its independent restore proof.")
            with engine.connect() as connection:
                connection.execute(text("SET TRANSACTION READ ONLY"))
                if proof["tables"] != snapshot(connection):
                    raise RuntimeError("Database differs from the independently restored backup; take and restore a fresh backup.")
                plan = plan_reset(connection, operation_id=args.operation_id, backup_path=str(backup),
                                  backup_sha256=backup_hash, operator=args.operator, reason=args.reason)
            args.plan.write_text(json.dumps(plan, indent=2) + "\n")
            args.plan.chmod(0o600)
            print(json.dumps({"plan": str(args.plan), "confirmation_sha256": plan["confirmation_sha256"], "delete_counts": plan["delete_counts"]}))
        else:
            if not args.plan:
                parser.error("execute requires --plan and --confirm")
            plan = json.loads(args.plan.read_text())
            if hashlib.sha256(Path(plan["backup_path"]).read_bytes()).hexdigest() != plan["backup_sha256"]:
                raise RuntimeError("The approved independent backup is missing or changed.")
            with engine.begin() as connection:
                print(json.dumps(execute_reset(connection, plan, confirm=args.confirm or "")))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
