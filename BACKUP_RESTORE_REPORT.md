# Backup and restore report

Date: 2026-10-03. Result: **PASS_AUTOMATED_ONLY** for backup, checksum, restore, migrations and application start on a populated copy; **BLOCKED** for MinIO storage and download; **NOT_TESTED** for the full-size database and for an off-machine copy.

Script: [`infrastructure/verify/backup-restore.sh`](infrastructure/verify/backup-restore.sh). Raw record: [`data/verification-backup-restore.json`](data/verification-backup-restore.json). The previous test used an empty database and produced a 448-byte file; this one does not.

## What ran (real components)

- postgres:17-alpine from docker-compose.prod.yml
- the backup service (infrastructure/scripts/backup-loop.sh)
- infrastructure/scripts/restore.sh
- infrastructure/postgres/10-app-role.sh and assign-ownership.sql
- the migrate and api images from the compose file

## Facts

| | |
|---|---|
| PostgreSQL | 17.11 (the image in `docker-compose.prod.yml`) |
| Migration revision | 20261003_0088 before and after |
| Database size before backup | 397,170,355 bytes; 369 tables; 543,946 rows |
| Backup file | `woi-20261003T161342Z.sql.gz` |
| Backup size | 72,817,232 bytes (gzip -9 of plain SQL) |
| Backup duration | 30 s |
| SHA-256 | `96a4661d9416ed2df2c2179de37b3b0f70d1c26b16b1fccac13bab183b69c019`; re-checked with `sha256sum -c` before restoring |
| gzip integrity | ok (`gzip -t`) |
| Restore target | a **fresh** PostgreSQL volume (the previous volume was destroyed first; it held 0 tables) |
| Restore duration | 22 s with the real `infrastructure/scripts/restore.sh` |
| Row counts | **identical** in all 369 tables (543,946 rows) |
| Content check | md5 of every ayah's reference and Arabic text identical before and after |
| Ownership / RLS | every table owned by `world_of_islam`; that role is not a superuser (`f`), so row-level security applies |
| Migration compatibility | `alembic upgrade head` exits 0 on the restored database |
| Application | API healthy on the restored database; {"surahs": 114, "mosques_visible": 19776, "mosque_coverage": "ALGERIA_ONLY"} |

## Data validation on the restored database

- PASS manifest
- PASS quran_text_has_verified_source
- PASS hadith_grades_have_sources
- PASS published_content_traces_to_approved_source
- PASS hidden_datasets_are_hidden
- PASS knowledge_records_have_metadata
- PASS directory_listings_have_metadata
- PASS no_duplicate_identifiers
- FAIL graph_relationships_have_provenance
- PASS manifest_record_counts_match
- FAIL domain_registry_matches_database
- PASS knowledge_references_resolve
- PASS no_duplicate_scholars_or_books
- PASS directory_fields_and_duplicates

The two FAIL lines are caused by the verification copy, not by the restore: it holds no tafsir rows and only the published subset of the passages table, so the graph-evidence and registry-count checks cannot match. The same two checks pass on the full development database (14/14).

## Limits (read these before relying on the backups)

- The populated database is a COPY of the development data without the three bulk tables' unpublished rows (tafsir_entries empty; source_passages and quran_ayah_translations hold only the published subset) because the VM has about 3 GB of free disk and the full database is 5.5 GB. The backup size and restore time are therefore those of a 397 MB database, not of the 5.5 GB one.
- validation 12/14: graph_relationships_have_provenance and domain_registry_matches_database fail ONLY because of that subset (no tafsir rows, filtered passages). The same checks pass 14/14 on the full development database.
- MinIO is not part of the backup design: backups are written to ./backups on the host and nothing uploads them to object storage. No upload/download of backups to MinIO was tested because MinIO could not be started (quay.io is refused).
- Run on this build VM, not on the production host; the production host's disk, PostgreSQL volume and off-machine copy of ./backups are untested.
