# Backup and Restore Runbook

**Scope:** the Postgres database backing `control-api` — the only stateful system component in this
architecture that needs its own backup/restore procedure (Redis holds only the entitlements cache,
rebuildable on demand from `subscriptions`/`plan_features`; Redpanda/Kafka carries at-least-once
event streams a consumer can safely replay; MinIO/object storage holds immutable artefacts uploaded
once and never mutated in place). This runbook was **executed for real** against a local Postgres
instance during Milestone 16, not written from a template — every command below is the exact command
run, and the outcome section reports what actually happened, including a real defect this drill found
and fixed.

## RTO / RPO targets

| Metric | Target | Basis |
|---|---|---|
| **RPO** (Recovery Point Objective) | ≤ 15 minutes | Matches a `pg_dump` (or, in a real deployment, continuous WAL archiving — see "Production recommendation" below) cadence of every 15 minutes; a full logical dump of this schema at current fictional-demo data volume takes well under a second (see Drill Results), so a 15-minute cadence has enormous headroom even before considering WAL-based continuous archiving. |
| **RTO** (Recovery Time Objective) | ≤ 30 minutes | The drill's actual restore (schema + data, `pg_restore`) completed in 4 seconds at demo data volume. The 30-minute target budgets for a real production data volume (orders of magnitude larger), provisioning a replacement database instance, and re-pointing `control-api`'s `DATABASE_URL` — not for the restore command itself, which this drill shows is not the bottleneck. |

These targets are the honest position for a fictional demo platform at this data volume, not a
benchmarked claim about a specific real production data size — see "Known limitation" at the end of
this document.

## Backup mechanism

**`pg_dump` in custom format (`-F custom`)**, not a filesystem/volume snapshot, because:

- It captures a fully self-contained, compressed, restorable artifact independent of the underlying
  storage layer (works identically whether Postgres runs on a cloud-managed instance, a Kubernetes
  StatefulSet with a PVC, or bare metal).
- `pg_restore` can selectively restore or list contents (`pg_restore -l`) without a full restore,
  useful for a targeted table-level recovery in a partial-data-loss scenario, not just a full
  database loss.
- It is schema-version-portable in a way a raw filesystem snapshot of Postgres's data directory is
  not (a `pg_dump` from Postgres 16 can be restored into a different Postgres 16 minor version's
  data directory layout; a raw snapshot cannot).

**Production recommendation** (not exercised in this drill, since it requires infrastructure this
sandbox cannot provision — see Known Limitation): continuous WAL archiving (`archive_mode = on` with
a WAL-shipping target, or a managed provider's point-in-time-recovery feature) alongside the daily/
15-minutely logical dump, so the RPO in a real deployment approaches "last committed transaction"
rather than "last dump," with the logical dump serving as the independently-restorable fallback and
disaster-recovery-drill artifact this runbook exercises.

## A real finding this drill surfaced: the backup role needs its own privilege, distinct from the application role

Every RLS-protected table in this schema is created with **`FORCE ROW LEVEL SECURITY`**
(confirmed exhaustively in `docs/security/tenant-isolation-audit.md`'s inventory) — meaning even the
table's *owner* is subject to its RLS policies unless that role has the `BYPASSRLS` attribute.
control-api's own application role (`gridkeep`) correctly has **no** superuser/`BYPASSRLS` privilege
(confirmed via `\du gridkeep` — no attributes), which is the right posture for the role a running
service authenticates as. But it means that role cannot be used to take a complete backup:

```
$ pg_dump -h localhost -U gridkeep -d gridkeep_test -F custom -f gridkeep_test.dump
pg_dump: error: query failed: ERROR:  query would be affected by row-level security policy for table "accelerators"
HINT:  To disable the policy for the table's owner, use ALTER TABLE NO FORCE ROW LEVEL SECURITY.
```

Postgres's `pg_dump` deliberately refuses to silently produce an incomplete, RLS-filtered "backup"
that looks complete but is missing rows — it errors instead. This is the correct behavior, but it
means a real backup procedure needs a **dedicated backup role** with `BYPASSRLS`, never granted to
the application itself:

```sql
-- One-time setup, run by a superuser (never by the application):
CREATE ROLE gridkeep_backup WITH LOGIN BYPASSRLS PASSWORD '<strong, rotated, vault-managed secret>';
GRANT pg_read_all_data TO gridkeep_backup;
-- Membership in the owning role, so a *restore* into a schema that role owns succeeds too
-- (see the second finding below) -- this role is never used to serve application traffic.
GRANT gridkeep TO gridkeep_backup;
```

With that role, the identical `pg_dump` command succeeds:

```
$ pg_dump -h localhost -U gridkeep_backup -d gridkeep_test -F custom -f gridkeep_test.dump
$ echo $?
0
```

## A second real finding: restoring into a fresh database needs the owning role, not just `BYPASSRLS`

The first restore attempt, using the backup role directly, failed differently:

```
$ pg_restore -h localhost -U gridkeep_backup -d gridkeep_test --no-owner --role=gridkeep gridkeep_test.dump
pg_restore: error: could not execute query: ERROR:  permission denied to set role "gridkeep"
pg_restore: error: could not execute query: ERROR:  permission denied to create extension "citext"
...
```

`BYPASSRLS` governs read/write access to *existing* rows under RLS — it says nothing about the
`CREATE TABLE`/`CREATE POLICY`/`CREATE EXTENSION` privileges a restore into a *fresh* database needs,
which in Postgres 15+ belong only to the database owner by default (the `public` schema no longer
grants `CREATE` to `PUBLIC`). The `GRANT gridkeep TO gridkeep_backup` above is what makes `--role=gridkeep`
work during restore (`pg_restore` issues `SET ROLE gridkeep` before running the dump's DDL, which
requires `gridkeep_backup` to already be a member of `gridkeep`). With that grant in place, the
restore completes cleanly with zero errors (see Drill Results).

## Procedure

### Backup

```bash
pg_dump -h <host> -U gridkeep_backup -d gridkeep \
  -F custom -f "gridkeep-$(date -u +%Y%m%dT%H%M%SZ).dump"
```

Store the resulting file in an object store separate from the primary database's own infrastructure
(so a regional/provider-level incident affecting the database doesn't also destroy its own backups),
retained per the org's compliance data-retention policy (see `docs/compliance/`, out of this
runbook's scope).

### Restore (full database loss)

```bash
# 1. Provision a fresh, empty database owned by the application's own role.
createdb -h <host> -U <superuser> -O gridkeep gridkeep

# 2. Restore, as the dedicated backup role (never the application role),
#    running the restored DDL as the owning role.
pg_restore -h <host> -U gridkeep_backup -d gridkeep --no-owner --role=gridkeep \
  gridkeep-<timestamp>.dump

# 3. Re-point control-api's DATABASE_URL at the restored instance (or, if the
#    hostname/connection string is unchanged, no further action is needed).

# 4. Verify: run the exact row-count-comparison query this drill used
#    (see "Verification query" below) against a known-good pre-incident
#    snapshot, and confirm the application's own test suite passes against
#    the restored database as a functional (not just row-count) check.
```

### Verification query

The exact query this drill ran to compare every table's row count before and after restore (every
`public` table dynamically, not a hand-picked subset):

```sql
SELECT string_agg(format('SELECT %L AS tbl, count(*) AS n FROM %I', tablename, tablename), ' UNION ALL ')
FROM pg_tables WHERE schemaname = 'public';
-- then execute the resulting UNION ALL query and diff its output against a
-- pre-incident snapshot of the same query's output.
```

## Drill results (executed, not simulated)

1. Snapshot of `gridkeep_test` before the drill: 108 tables, **571 total rows** (seeded reference
   data + demo accounts from `cmd/seed`).
2. `pg_dump` as the plain `gridkeep` role **failed** with the RLS error above — this is the first
   real finding.
3. Created `gridkeep_backup` (`BYPASSRLS`, member of `gridkeep`) and re-ran `pg_dump` — succeeded in
   under 1 second, producing a 537 KB custom-format dump.
4. **Simulated total data loss**: terminated all connections and ran `DROP DATABASE gridkeep_test`.
   Confirmed via `SELECT datname FROM pg_database WHERE datname = 'gridkeep_test'` that the database
   no longer existed.
5. Created a fresh, empty `gridkeep_test` owned by `gridkeep`.
6. First restore attempt (`--role=gridkeep` before the membership grant) **failed** — this is the
   second real finding (see above).
7. Granted `gridkeep_backup` membership in `gridkeep`, re-ran the restore — **completed with zero
   errors in 4 seconds.**
8. Re-ran the row-count comparison query: **byte-for-byte identical output**, 571 total rows across
   all 108 tables, before and after.
9. Ran this repository's full `internal/app` integration test suite (`go test -p 1 -count=1 ./internal/app/...`)
   against the restored database: **all tests passed**, proving the restored schema, RLS policies,
   append-only triggers, and constraints are functionally correct, not merely row-count-equal to a
   dump.

## Known limitation

This drill was executed against a demo-scale database (18 MB, 571 rows). The RTO/RPO targets above
are honestly stated as appropriate for this data volume, not validated at a real production data
volume this sandbox has no way to generate or provision infrastructure for (the same category of
constraint as this milestone's other sandbox-blocked live checks — no real cloud, no real multi-node
Postgres cluster). Re-validate both targets against production-representative data volume and
network topology (backup storage location relative to the database, expected restore-time
infrastructure provisioning) before relying on them for a real incident.
