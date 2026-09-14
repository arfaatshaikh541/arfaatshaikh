# World of Islam Migration Fix Report

## Fixed defects

1. `20260725_0008_registry_hardening.py`
   - Split PostgreSQL function creation and trigger creation into separate `op.execute()` calls for asyncpg compatibility.

2. `20260725_0009_quran_foundation.py`
   - Added explicit unique-constraint names for the two `quran_ayahs` constraints that both begin with `text_edition_id`.

3. `20260725_0010_quran_import_pipeline.py`
   - Split PostgreSQL function creation and trigger creation into separate `op.execute()` calls.
   - Split downgrade trigger and function removal into separate `op.execute()` calls.
   - Kept all operations inside `upgrade()` and `downgrade()`.

4. `20260725_0014_hadith_foundation.py`
   - Added explicit unique-constraint names for the two `hadith_narrations` constraints that both begin with `collection_id`.

5. `20260725_0015_hadith_import_pipeline.py`
   - Split PostgreSQL function creation and trigger creation into separate `op.execute()` calls for asyncpg compatibility.

## Verification performed

- Compiled all 81 migration Python files successfully.
- Compiled Python sources under `apps` and `packages` successfully.
- Parsed every JSON file successfully.
- Audited every migration for module-scope Alembic operations.
- Audited every `op.create_table()` for colliding unnamed unique constraints.
- Audited every literal `op.execute()` for combined function/trigger and trigger/function-drop statements.

## Runtime verification note

Docker is unavailable in the artifact-building environment, so the full PostgreSQL/Alembic runtime chain could not be executed here. Run the commands below on the EC2 host.

```bash
cd ~/products/world-of-islam
docker compose build --no-cache migrate
docker compose run --rm migrate
docker compose up -d
docker compose ps -a
```

Do not run `docker compose down -v` unless database deletion is intentional.
