#!/bin/sh
# Nightly PostgreSQL backup. Runs inside the `backup` service; writes compressed dumps to /backups.
set -eu
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
while true; do
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  out="/backups/woi-${stamp}.sql.gz"
  if pg_dump --no-owner --format=plain | gzip -9 > "${out}.partial"; then
    mv "${out}.partial" "${out}"
    echo "backup ok: ${out} ($(wc -c < "${out}") bytes)"
  else
    rm -f "${out}.partial"
    echo "backup FAILED at ${stamp}" >&2
  fi
  find /backups -name 'woi-*.sql.gz' -mtime "+${KEEP_DAYS}" -delete
  sleep 86400
done
