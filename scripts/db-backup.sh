#!/usr/bin/env bash
set -euo pipefail

out_dir="${BACKUP_DIR:-${HOME}/.local/share/uni-shortlist/backups}"
umask 077
mkdir -p "$out_dir"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="$out_dir/uni_shortlist_${stamp}.dump"
metadata="$backup.meta"

# Read-only transaction verifies the actual development target and snapshots counts.
read -r identity < <(docker compose exec -T db sh -c 'export PGPASSWORD="$POSTGRES_PASSWORD"; exec psql -X -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -F "|"' <<'SQL'
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
       (SELECT count(*) FROM audit_events);
COMMIT;
SQL
)
IFS='|' read -r db role revision universities programs users profiles runs saved facts versions evidence jobs audits <<<"$identity"
if [[ "$db" != "uni_shortlist" || "$role" != "uni_shortlist" || -z "$revision" ]]; then
  echo "Refusing backup: actual database identity is not the expected development target." >&2
  exit 1
fi

if ! docker compose exec -T db sh -c 'export PGPASSWORD="$POSTGRES_PASSWORD"; exec pg_dump --format=custom --no-owner --no-acl -U "$POSTGRES_USER" -d "$POSTGRES_DB"' > "$backup"; then
  rm -f "$backup"
  echo "Backup failed; incomplete dump removed." >&2
  exit 1
fi
chmod 600 "$backup"
cat > "$metadata" <<EOF
created_at_utc=$stamp
database=$db
role=$role
alembic_revision=$revision
universities=$universities
programs=$programs
users=$users
student_profiles=$profiles
recommendation_runs=$runs
saved_programs=$saved
fact_records=$facts
fact_versions=$versions
fact_evidence=$evidence
ingestion_jobs=$jobs
audit_events=$audits
EOF
chmod 600 "$metadata"
printf 'Backup created: %s\nMetadata: %s\n' "$backup" "$metadata"
