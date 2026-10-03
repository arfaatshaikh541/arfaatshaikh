#!/usr/bin/env bash
# Verify the REAL backup and restore path (infrastructure/scripts/backup-loop.sh and restore.sh, PostgreSQL 17 from docker-compose.prod.yml)
# on a POPULATED database, and write the facts to $OUT (JSON lines). Run from the repository root with .env.production present and a
# development database to copy from (SOURCE_DB, default woi_work, on the local PostgreSQL).
#
#   infrastructure/verify/backup-restore.sh
#
# Steps: fresh postgres -> load populated data -> record counts -> run the backup service -> checksum -> destroy the volume ->
# fresh postgres -> restore.sh -> compare counts -> migrations -> validate_data.py as the application role -> start the api against it.
# MinIO is not involved: the current design writes backups to ./backups on the host; nothing uploads them to object storage.
set -euo pipefail
cd "$(dirname "$0")/../.."
SOURCE_DB="${SOURCE_DB:-woi_work}"
OUT="${OUT:-/tmp/backup-restore.jsonl}"; : > "$OUT"
WORK="$(mktemp -d)"
set -a; . ./.env.production; set +a
cat > "$WORK/override.yml" <<'Y'
services:
  minio: {profiles: ["blocked-quay-403"]}
  minio-init: {profiles: ["blocked-quay-403"]}
  api: {depends_on: !override {migrate: {condition: service_completed_successfully}, redis: {condition: service_healthy}}}
Y
DC=(docker compose --env-file .env.production -f docker-compose.prod.yml -f "$WORK/override.yml")
PSQL=("${DC[@]}" exec -T postgres psql -v ON_ERROR_STOP=1 -q -At -U "$POSTGRES_USER" -d "$POSTGRES_DB")
say() { printf '%s\n' "$1" | tee -a "$OUT" >&2; }
wait_pg() { until [ "$("${DC[@]}" ps postgres --format '{{.Health}}')" = healthy ]; do sleep 2; done; }
COUNTS_SQL="select table_name||'='||(xpath('/row/c/text()', query_to_xml(format('select count(*) as c from %I.%I', table_schema, table_name), false, true, '')))[1]::text from information_schema.tables where table_schema='public' and table_type='BASE TABLE' order by 1"
BIG=(source_passages quran_ayah_translations tafsir_entries)

"${DC[@]}" down -v >/dev/null 2>&1 || true
rm -f backups/woi-*.sql.gz
"${DC[@]}" up -d --no-build postgres >/dev/null; wait_pg

# 1. load the populated database (all tables; the three bulk tables carry only the published subset, for disk space)
EX=(); for t in "${BIG[@]}"; do EX+=(--exclude-table-data="$t"); done
su postgres -c "pg_dump -Fc --no-owner --no-privileges ${EX[*]} $SOURCE_DB" > "$WORK/load.dump"
PGC="$("${DC[@]}" ps -q postgres)"
docker cp "$WORK/load.dump" "$PGC:/tmp/load.dump"
docker exec "$PGC" psql -q -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" >/dev/null
docker exec "$PGC" pg_restore --no-owner --no-privileges -j 4 -U "$POSTGRES_USER" -d "$POSTGRES_DB" /tmp/load.dump >/dev/null 2>&1 || true
KEEP="select id from source_editions where edition_key in ('hafs-uthmani-quran-text-v3','eng-mohammedmarmadu','eng-yusufaliorig') or edition_key like 'sahih-%' or edition_key like 'nawawi%' or edition_key like 'hisn%' or edition_key like 'adhkar%'"
copy_in() { (echo "SET session_replication_role = replica;"; echo "COPY $1 FROM STDIN;"; su postgres -c "psql -q -c \"COPY (select * from $1 where $2) TO STDOUT\" $SOURCE_DB"; echo '\.') | "${PSQL[@]}" >/dev/null; }
copy_in source_passages "edition_id in ($KEEP)"
copy_in quran_ayah_translations "translation_edition_id in (select id from quran_translation_editions where published)"
"${DC[@]}" exec -T postgres psql -v ON_ERROR_STOP=1 -q -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v app="\"$WOI_APP_DB_USER\"" < infrastructure/postgres/assign-ownership.sql >/dev/null
docker exec "$PGC" rm -f /tmp/load.dump

# 2. facts before the backup
"${PSQL[@]}" -c "$COUNTS_SQL" | sort > "$WORK/counts.before"
HASH_SQL="select md5(string_agg(canonical_reference||arabic_text, '|' order by canonical_reference)) from quran_ayahs"
say "{\"stage\":\"before\",\"postgres\":\"$("${PSQL[@]}" -c 'show server_version')\",\"alembic\":\"$("${PSQL[@]}" -c 'select version_num from alembic_version')\",\"database_bytes\":$("${PSQL[@]}" -c 'select pg_database_size(current_database())'),\"tables\":$(wc -l < "$WORK/counts.before"),\"rows\":$(awk -F= '{s+=$2} END{print s}' "$WORK/counts.before"),\"ayah_md5\":\"$("${PSQL[@]}" -c "$HASH_SQL")\"}"

# 3. the real backup job (infrastructure/scripts/backup-loop.sh, as the `backup` service runs it)
T0=$(date +%s)
"${DC[@]}" up -d --no-build backup >/dev/null
until "${DC[@]}" logs backup 2>&1 | grep -q "backup ok\|backup FAILED"; do sleep 3; done
BACKUP_SECONDS=$(( $(date +%s) - T0 ))
"${DC[@]}" logs backup 2>&1 | grep -q "backup FAILED" && { say '{"stage":"backup","result":"FAILED"}'; exit 1; }
"${DC[@]}" stop backup >/dev/null
FILE="$(ls backups/woi-*.sql.gz | tail -1)"
gzip -t "$FILE"
say "{\"stage\":\"backup\",\"file\":\"$(basename "$FILE")\",\"bytes\":$(wc -c < "$FILE"),\"sha256\":\"$(sha256sum "$FILE" | cut -d' ' -f1)\",\"gzip_integrity\":\"ok\",\"seconds\":$BACKUP_SECONDS}"
sha256sum "$FILE" > "$FILE.sha256"

# 4. destroy the database volume, build a fresh one, restore with the real restore.sh
"${DC[@]}" down -v >/dev/null 2>&1
"${DC[@]}" up -d --no-build postgres >/dev/null; wait_pg
sha256sum -c "$FILE.sha256" >/dev/null
EMPTY=$("${PSQL[@]}" -c "select count(*) from information_schema.tables where table_schema='public'")
T1=$(date +%s)
echo RESTORE | COMPOSE_FILES="" bash -c "
  sed 's#docker compose --env-file .env.production -f docker-compose.prod.yml#docker compose --env-file .env.production -f docker-compose.prod.yml -f $WORK/override.yml#' infrastructure/scripts/restore.sh > $WORK/restore.sh && sh $WORK/restore.sh $FILE" >/dev/null
RESTORE_SECONDS=$(( $(date +%s) - T1 ))
"${PSQL[@]}" -c "$COUNTS_SQL" | sort > "$WORK/counts.after"
if diff -q "$WORK/counts.before" "$WORK/counts.after" >/dev/null; then COUNTS=identical; else COUNTS=DIFFERENT; diff "$WORK/counts.before" "$WORK/counts.after" | head -10 >&2; fi
say "{\"stage\":\"restore\",\"fresh_database_tables_before\":$EMPTY,\"seconds\":$RESTORE_SECONDS,\"row_counts\":\"$COUNTS\",\"tables\":$(wc -l < "$WORK/counts.after"),\"rows\":$(awk -F= '{s+=$2} END{print s}' "$WORK/counts.after"),\"alembic\":\"$("${PSQL[@]}" -c 'select version_num from alembic_version')\",\"ayah_md5\":\"$("${PSQL[@]}" -c "$HASH_SQL")\"}"
OWNER=$("${PSQL[@]}" -c "select string_agg(distinct tableowner, ',') from pg_tables where schemaname='public'")
say "{\"stage\":\"ownership\",\"table_owner\":\"$OWNER\",\"app_role_is_superuser\":\"$("${PSQL[@]}" -c "select rolsuper from pg_roles where rolname='$WOI_APP_DB_USER'")\"}"

# 5. migrations, data validation as the application role, application start
"${DC[@]}" run --rm --no-deps migrate >"$WORK/migrate.log" 2>&1 && say '{"stage":"migrations","result":"alembic upgrade head exits 0 on the restored database"}' || { say '{"stage":"migrations","result":"FAILED"}'; tail -5 "$WORK/migrate.log" >&2; }
# inside the stack network (the backend network is internal, so a host-side client cannot reach the database), as the application role
VAL=$("${DC[@]}" run --rm --no-deps -T api python scripts/validate_data.py 2>&1 || true)
echo "$VAL" > "${OUT%.jsonl}.validation.txt"
NPASS=$(echo "$VAL" | grep -c '^PASS' || true); NFAIL=$(echo "$VAL" | grep -c '^FAIL' || true)
if [ $((NPASS + NFAIL)) -eq 0 ]; then say '{"stage":"validation","result":"ERROR: the validator produced no result; see the .validation.txt next to this file"}'; exit 1; fi
say "{\"stage\":\"validation\",\"as_role\":\"$WOI_APP_DB_USER\",\"passed\":$NPASS,\"failed\":$NFAIL}"
"${DC[@]}" up -d --no-build redis api >/dev/null
for i in $(seq 1 30); do [ "$("${DC[@]}" ps api --format '{{.Health}}')" = healthy ] && break; sleep 3; done
API=$("${DC[@]}" exec -T api python - <<'P'
import json,urllib.request
def get(p):
    return json.load(urllib.request.urlopen("http://127.0.0.1:8000"+p, timeout=30))
s=get("/api/v1/quran/surahs"); c=get("/api/v1/knowledge/coverage"); d=get("/api/v1/directory/summary")
print(json.dumps({"surahs":len(s),"mosques_visible":next(t["count"] for t in d["types"] if t["type"]=="mosque"),"mosque_coverage":next(x["coverage_status"] for x in c["domains"] if x["domain"]=="mosques")}))
P
)
say "{\"stage\":\"application\",\"health\":\"$("${DC[@]}" ps api --format '{{.Health}}')\",\"reads\":$API}"
"${DC[@]}" down -v >/dev/null 2>&1 || true
rm -rf "$WORK"
