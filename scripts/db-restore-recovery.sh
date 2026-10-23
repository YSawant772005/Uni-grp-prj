#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || ! -f "$1" || ! -f "$1.meta" ]]; then
  echo "Usage: bash scripts/db-restore-recovery.sh /path/to/uni_shortlist_TIMESTAMP.dump" >&2
  exit 2
fi
backup="$(realpath "$1")"
metadata="$backup.meta"
project="${RECOVERY_PROJECT_NAME:-uni-shortlist-recovery}"
compose=(docker compose -p "$project" -f docker-compose.recovery.yml --profile recovery)

"${compose[@]}" up -d db-recovery
for _ in $(seq 1 60); do
  if "${compose[@]}" exec -T db-recovery pg_isready -U uni_shortlist_recovery -d uni_shortlist_recovery >/dev/null 2>&1; then break; fi
  sleep 1
done

read -r target < <("${compose[@]}" exec -T db-recovery sh -c 'export PGPASSWORD="$POSTGRES_PASSWORD"; exec psql -X -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -F "|"' <<'SQL'
BEGIN READ ONLY;
SET LOCAL statement_timeout = '10s';
SELECT current_database(), current_user,
       (SELECT marker FROM unishortlist_recovery.instance_marker LIMIT 1);
COMMIT;
SQL
)
if [[ "$target" != "uni_shortlist_recovery|uni_shortlist_recovery|uni-shortlist-isolated-recovery-db-v1" ]]; then
  echo "Refusing restore: target identity is not the disposable recovery instance." >&2
  exit 1
fi

if ! "${compose[@]}" exec -T db-recovery sh -c 'export PGPASSWORD="$POSTGRES_PASSWORD"; exec pg_restore --exit-on-error --clean --if-exists --no-owner --no-acl -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$backup"; then
  echo "Restore failed in the isolated recovery database." >&2
  exit 1
fi

read -r restored < <("${compose[@]}" exec -T db-recovery sh -c 'export PGPASSWORD="$POSTGRES_PASSWORD"; exec psql -X -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -F "|"' <<'SQL'
BEGIN READ ONLY;
SET LOCAL statement_timeout = '10s';
SELECT current_database(), current_user,
       (SELECT version_num FROM alembic_version LIMIT 1),
       (SELECT count(*) FROM universities),
       (SELECT count(*) FROM programs),
       (SELECT count(*) FROM users),
       (SELECT count(*) FROM student_profiles),
       (SELECT count(*) FROM recommendation_runs),
       (SELECT count(*) FROM saved_programs),
       (SELECT count(*) FROM fact_records),
       (SELECT count(*) FROM fact_versions),
       (SELECT count(*) FROM fact_evidence),
       (SELECT count(*) FROM ingestion_jobs),
       (SELECT count(*) FROM audit_events),
       (SELECT marker FROM unishortlist_recovery.instance_marker LIMIT 1);
COMMIT;
SQL
)
declare -A expected
while IFS='=' read -r key value; do expected["$key"]="$value"; done < "$metadata"
IFS='|' read -r restored_db restored_role restored_revision universities programs users profiles runs saved facts versions evidence jobs audits marker <<<"$restored"
if [[ "$restored_db" != "uni_shortlist_recovery" || "$restored_role" != "uni_shortlist_recovery" ||
      "$marker" != "uni-shortlist-isolated-recovery-db-v1" ||
      "$restored_revision" != "${expected[alembic_revision]}" ||
      "$universities" != "${expected[universities]}" || "$programs" != "${expected[programs]}" ||
      "$users" != "${expected[users]}" || "$profiles" != "${expected[student_profiles]}" ||
      "$runs" != "${expected[recommendation_runs]}" || "$saved" != "${expected[saved_programs]}" ||
      "$facts" != "${expected[fact_records]}" || "$versions" != "${expected[fact_versions]}" ||
      "$evidence" != "${expected[fact_evidence]}" || "$jobs" != "${expected[ingestion_jobs]}" ||
      "$audits" != "${expected[audit_events]}" ]]; then
  echo "Recovery verification failed: target identity, Alembic revision, or aggregate counts differ." >&2
  exit 1
fi
printf 'Recovery verified in isolated tmpfs database; revision=%s, universities=%s, programs=%s, facts=%s.\n' \
  "$restored_revision" "$universities" "$programs" "$facts"
echo 'The recovery container remains isolated and disposable; stop it when finished.'
