"""Write WORLD_OF_ISLAM_FINAL_REPORT.md, BACKUP_RESTORE_REPORT.md and AI_VERIFICATION_REPORT.md from the machine-readable results.

    uv run python scripts/write_final_report.py

Run scripts/export_final_reports.py first (it writes DATA_READINESS_FINAL.json and PRODUCTION_VERIFICATION_FINAL.json, which this reads).
The first line of the main report is exactly one of PRODUCTION_READY / NOT_PRODUCTION_READY and is taken from the computed verdict, never typed.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
J = lambda name: json.loads((ROOT / name).read_text(encoding="utf-8"))  # noqa: E731
ready, prod, cover, sources = J("DATA_READINESS_FINAL.json"), J("PRODUCTION_VERIFICATION_FINAL.json"), J("DATA_COVERAGE_FINAL.json"), J("SOURCE_VERIFICATION_FINAL.json")
backup, comp, sec = J("data/verification-backup-restore.json"), J("data/verification-prod-compose.json"), J("data/verification-security.json")
probes = {r["source_id"]: r for r in sources["probes"]["records"]}
verdict = prod["overall_status"]
n = lambda x: f"{x:,}"  # noqa: E731


def probe_row(label: str, source_id: str) -> str:
    r = probes[source_id]
    m = r["requests"]["main"]
    result = "REACHABLE" if r["accessible"] else "BLOCKED by egress policy (403 on CONNECT)" if "403" in (m.get("error") or "") else (m.get("error") or "unreachable")[:60]
    dns = "ok" if r["dns"].get("ok") else "failed"
    tls = (m.get("tls") or {}).get("protocol", "-") if isinstance(m.get("tls"), dict) else "-"
    return (f"| {label} | {r['host']} | {dns} | {tls} | {m.get('status') or '-'} | {r['licence_page_accessible']} | {r['terms_accessible']} | {r['data_accessible']} | {r['last_checked'][:16]} | {result} |")


NAMED = [("Wikidata", "wikidata"), ("OpenStreetMap / Overpass", "openstreetmap-overpass"), ("Open Library", "open-library"), ("Internet Archive", "internet-archive"),
         ("Project Gutenberg", "project-gutenberg"), ("Charity Commission (E&W)", "charity-commission-ew"), ("OSCR (Scotland)", "oscr-scotland"), ("ACNC (Australia)", "acnc-australia"),
         ("Job API: Adzuna", "adzuna-api"), ("Job API: Arbeitnow", "arbeitnow-api"), ("Recitations: mp3quran", "mp3quran"), ("Recitations: EveryAyah", "everyayah"), ("sunnah.com API", "sunnah-com-api"),
         ("Ollama model registry", "ollama-registry"), ("quay.io (MinIO images)", "quay-io-minio"), ("The real URL (app.arfaat.com)", "app-arfaat-com"), ("Docker Hub registry", "docker-hub-registry"),
         ("PyPI", "pypi"), ("npm registry", "npm-registry")]
probe_table = "\n".join(probe_row(a, b) for a, b in NAMED)

comp_rows = "\n".join(f"| {c['component']} | **{c['result']}** | {c['evidence']} | {c['tested_on']} |" for c in prod["components"])
blockers = "\n".join(f"{i}. {b}" for i, b in enumerate(prod["blockers"], 1))
dom_rows = "\n".join(f"| {d['label']} | **{d['status']}** | {n(d['records']['total'])} | {n(d['records']['published'])} | {n(d['records']['hidden'])} | "
                     f"{', '.join(sorted({x['rights_decision'] for x in d['datasets']} - {'NO_LEDGER_ENTRY'})) or 'no dataset'} | "
                     f"{next(c for c in cover['domains'] if c['domain'] == d['domain'])['coverage_status']} |" for d in ready["domains"])
b = {x["stage"]: x for x in backup["stages"]}
suites = comp["browser_suites"]

main = f"""{verdict}

# World of Islam: final report (blocker-resolution phase)

Date: 2026-10-03. Branch `claude/world-of-islam-webapp-9rfzue`. Machine-readable: [`PRODUCTION_VERIFICATION_FINAL.json`](PRODUCTION_VERIFICATION_FINAL.json), [`DATA_READINESS_FINAL.json`](DATA_READINESS_FINAL.json), [`SOURCE_VERIFICATION_FINAL.json`](SOURCE_VERIFICATION_FINAL.json), [`DATA_COVERAGE_FINAL.json`](DATA_COVERAGE_FINAL.json). Companion reports: [`BACKUP_RESTORE_REPORT.md`](BACKUP_RESTORE_REPORT.md), [`AI_VERIFICATION_REPORT.md`](AI_VERIFICATION_REPORT.md).

Status vocabulary used throughout: **PASS** (worked as designed where it was tested), **PASS_AUTOMATED_ONLY** (passed automated checks; no human or independent review), **PARTIAL**, **BLOCKED** (cannot be done from this environment, with the reason), **NOT_TESTED**, **NOT_APPLICABLE**.

## 1. Why the status did not change

The previous report's blockers were mostly about **where** this work runs, not about missing code. This session ran in the same build VM as before, not on the deployment host:

- Outbound access is governed by an egress policy that answers **403 to CONNECT** for every host except PyPI, npm and the GitHub/Docker Hub registries. Re-probed from this VM with `scripts/probe_sources.py` on 2026-10-03 (section 3): nothing changed. I did not route around the policy.
- `app.arfaat.com` is refused by the same policy, and the certificate in `/etc/letsencrypt/live/app.arfaat.com` is the **self-signed** one created for testing. **No test in this report ran against the real domain.** Every browser check used a local hosts mapping.
- `quay.io` is refused, so MinIO and `minio-init` could not start. `registry.ollama.ai` is refused, so no model could be installed.

So Priorities 1, 2, 3, 4 (model), 7, 8 and 10 are **BLOCKED**, and I did not mark anything green to hide that. What could be done without the network was done and is reported below.

## 2. Exact blockers for PRODUCTION_READY

Every critical item that did not pass:

{blockers}

## 3. Network probe (Priority 1)

Run from this VM on 2026-10-03 with `scripts/probe_sources.py` ({sources['probes']['summary']['total']} targets: {sources['probes']['summary']['accessible']} accessible, {sources['probes']['summary']['data_accessible']} with reachable data). Full records, including robots.txt and rights notes for all targets, are in [`data/source-probes.json`](data/source-probes.json).

| Source | Host | DNS | TLS | HTTP | Licence page | Terms page | Data | Last checked (UTC) | Result |
|---|---|---|---|---|---|---|---|---|---|
{probe_table}

DNS resolves for every host; TLS and HTTP are never reached because the egress gateway refuses the tunnel. The licence and terms columns are therefore `False`/`None` (not read), not "absent". **Nothing was imported from any source in this phase**, and no licence or terms were read for any newly reachable source, because none became reachable. Docker Hub answers 401 to an unauthenticated registry call, which is the normal reachable response (it is also rate limiting image pulls with 429 at times).

## 4. What was built and verified without the network

| Priority | Result | Detail |
|---|---|---|
| 5. Celery worker | **PASS** | The worker registered **no** tasks before. It now registers three, each doing work the application already needs: `woi.email.send_outbox` (verification and password-reset mail was queued in `email_outbox` but **nothing ever sent it**; now sent over SMTP, tokens removed after delivery, stale mail expired, 5 retries with backoff on a mail outage), `woi.auth.purge_expired` (retention clean-up of sessions, tokens and sent mail), `woi.data.validate` (daily data-governance validation, one audit row per run; 14 checks in about 150 s on 6.5 M rows). No placeholder tasks; scheduled imports were deliberately not added because an unattended import would publish without review. `celery inspect registered` inside the container lists exactly these three; beat runs in the same process. End to end on a populated database: a real registration queued mail, the worker delivered it through an SMTP server, the emailed token verified the account, and a second use was refused. |
| 6. Backups | **PASS_AUTOMATED_ONLY** | Section 6 and [`BACKUP_RESTORE_REPORT.md`](BACKUP_RESTORE_REPORT.md): the real backup service and `restore.sh` on a populated PostgreSQL 17; identical row counts and Qur'an hash after restore. **Not** stored in MinIO (not part of the design; MinIO is blocked), and the 5.5 GB database itself could not be restored here (3 GB of free disk). |
| 9. Qur'an rights | **PARTIAL** | New evidence recorded in the ledger (section 5). Decisions unchanged: still `PUBLISH_WITH_CAVEAT`. |
| 11. Mosques | **PASS** | Coverage now carries `ALGERIA_ONLY`, `COMMUNITY_DATA` and `NOT_INDIVIDUALLY_VERIFIED` (derived from live verification counts) and the status page says so. The 8 / 282 / 38 flagged items are untouched in the review queue. |
| 12. Arabic review | **BLOCKED** (needs a person) | Workflow built and tested: string, context (the source line), English source, Arabic, category, status, reviewer, timestamp, native-reader attestation required, change requests need detail, a re-sync keeps decisions and suggestions (a bug that erased suggestions was fixed), CSV hand-off for an offline reader. **0 of 168 approved.** |
| 13. Security | **PASS_AUTOMATED_ONLY** | Label: **AUTOMATED_SECURITY_TESTED**. Section 7. |
| AI labels | **PASS** | LOCAL AI, MODEL and SOURCE EVIDENCE are now shown by the UI and carried by the API (section 8). |

## 5. Quran rights (Priority 9) and hadith / tafsir (Priority 10)

Unchanged and still honest: Qur'an datasets `PUBLISH_WITH_CAVEAT`; hadith text, hadith gradings and tafsir `KEEP_HIDDEN` (nothing deleted). The only new evidence obtainable through the reachable registries concerned **tajweed**:

- The `@quran.ws/tajwid-annotations` and `-rules` packages carry a licence file naming **Quranpedia** as copyright holder and granting CC BY 4.0, with a **mandatory credit line**: `Tajweed Rule Corpus, Quranpedia - https://github.com/quranpedia/tajweed-engine`. The reader previously credited "quran.ws"; it now carries the required credit, the licence link, and a statement that the rules were not changed.
- The annotations contain offsets and rule ids only (no Qur'anic text) and pin the text they were measured against by a SHA-256 digest. **I could not reproduce that digest** from the text this platform publishes (24 plain serialisations tried); the serialisation is defined in a repository that is not reachable. The importer's own checks (spans within bounds, qalqalah on qalqalah letters) stand; a digest match does not.
- Open questions recorded: the publisher account (`quranws`) differs from the named copyright holder, and the two repositories named (`quran-ws/quran-tajweed` in the package, `quranpedia/tajweed-engine` in the credit) were both unreachable.
- Nothing new could be established for the Arabic text, Pickthall or Yusuf Ali, hadith editions, grading works or tafsir editions: their upstream repositories and publishers' sites are behind the egress policy. No caveat was removed.

## 6. Backup and restore (Priority 6)

Details and the raw record: [`BACKUP_RESTORE_REPORT.md`](BACKUP_RESTORE_REPORT.md), [`data/verification-backup-restore.json`](data/verification-backup-restore.json).

| Measure | Value |
|---|---|
| Database | PostgreSQL {b['before']['postgres']}, revision {b['before']['alembic']}, {n(b['before']['database_bytes'])} bytes, {b['before']['tables']} tables, {n(b['before']['rows'])} rows (populated copy) |
| Backup | `{b['backup']['file']}`, {n(b['backup']['bytes'])} bytes, {b['backup']['seconds']} s, gzip integrity {b['backup']['gzip_integrity']} |
| SHA-256 | `{b['backup']['sha256']}` (verified again before the restore) |
| Restore into a fresh volume | {b['restore']['seconds']} s with the real `restore.sh`; row counts **{b['restore']['row_counts']}** in all {b['restore']['tables']} tables; Qur'an text hash identical |
| Migrations on the restored database | `alembic upgrade head` exits 0 |
| Validation | 12 of 14 pass; the two failures come from the disk-limited copy (no tafsir rows), and the same checks pass 14/14 on the full database |
| Application | API healthy on the restored database; reads return 114 surahs and 19,776 visible mosque listings |
| MinIO storage / download of backups | **BLOCKED / NOT_TESTED** |

## 7. Security (Priority 13): AUTOMATED_SECURITY_TESTED

{sec['summary']}

No independent penetration test took place. DoS, WAF and the real host were not tested.

## 8. AI (Priority 4)

Full account: [`AI_VERIFICATION_REPORT.md`](AI_VERIFICATION_REPORT.md). In short: the Ollama service runs; **no model could be installed**; the platform says so (LOCAL AI, model name, "no local model is running") and still returns quoted, cited evidence; with no sufficient source it abstains. The model-dependent path (retrieval, source filtering, **Ollama**, citation validation) is **NOT_TESTED** with a real model; citation validation is tested against model output supplied by tests (fabricated citations are rejected).

## 9. Production verification run ({comp['date']})

Stack: the real `docker-compose.prod.yml` on this VM with MinIO disabled (the only deviations are listed in [`data/verification-prod-compose.json`](data/verification-prod-compose.json)). Real Chromium against `https://app.arfaat.com/worldofislam` **through a hosts mapping and a self-signed certificate** (not the real domain): `browser-verify.cjs` {suites['browser-verify.cjs']['passed']} passed / {suites['browser-verify.cjs']['failed']} failed; `prod-extra-verify.cjs` {suites['prod-extra-verify.cjs']['passed']} passed / {suites['prod-extra-verify.cjs']['failed']} failed. Every failure observed during the phase is recorded in section 11.

| Component / criterion | Result | Evidence | Tested on |
|---|---|---|---|
{comp_rows}

## 10. Data domains

| Domain | Status | Records | Published | Hidden | Rights decision | Coverage |
|---|---|---:|---:|---:|---|---|
{dom_rows}

No domain is READY. No data was added in this phase; no hidden dataset was published or deleted.

## 11. Failures and defects found and fixed in this phase

{chr(10).join('- ' + x for x in comp['defects_found'])}

## 12. Known limitations

- Rights reasoning is mine from the cited sources; no lawyer reviewed it. No scholar reviewed any religious content. No native reader approved any Arabic string. None of this is fabricated or implied.
- Test counts: API {ready['tests']['api']}, web {ready['tests']['web']}, typecheck and ESLint clean.
- `/patch_reports.py` is an empty file I created by mistake in the filesystem root of this VM; it could not be removed from here and is not part of the repository.

## 13. Next actions (in order)

1. Run this repository on the **deployment host** with the compose file unmodified: `docker pull` the two quay.io images, `docker compose exec ollama ollama pull <model>`, then `infrastructure/verify/backup-restore.sh`, `browser-verify.cjs` and `prod-extra-verify.cjs` against `https://app.arfaat.com/worldofislam`, and `scripts/probe_sources.py`.
2. Set `WOI_SMTP_*` so users can verify email and reset passwords.
3. Decide the rights questions (Qur'an text publisher, hadith editions, grading works, tafsir editions, ODbL share-alike for mosques); a native Arabic reader works the 168 strings in "Human review".
4. Only then import further domains, reading each source's licence and terms first.
"""
(ROOT / "WORLD_OF_ISLAM_FINAL_REPORT.md").write_text(main, encoding="utf-8")

(ROOT / "BACKUP_RESTORE_REPORT.md").write_text(f"""# Backup and restore report

Date: 2026-10-03. Result: **PASS_AUTOMATED_ONLY** for backup, checksum, restore, migrations and application start on a populated copy; **BLOCKED** for MinIO storage and download; **NOT_TESTED** for the full-size database and for an off-machine copy.

Script: [`infrastructure/verify/backup-restore.sh`](infrastructure/verify/backup-restore.sh). Raw record: [`data/verification-backup-restore.json`](data/verification-backup-restore.json). The previous test used an empty database and produced a 448-byte file; this one does not.

## What ran (real components)

{chr(10).join('- ' + x for x in backup['real_components'])}

## Facts

| | |
|---|---|
| PostgreSQL | {b['before']['postgres']} (the image in `docker-compose.prod.yml`) |
| Migration revision | {b['before']['alembic']} before and after |
| Database size before backup | {n(b['before']['database_bytes'])} bytes; {b['before']['tables']} tables; {n(b['before']['rows'])} rows |
| Backup file | `{b['backup']['file']}` |
| Backup size | {n(b['backup']['bytes'])} bytes (gzip -9 of plain SQL) |
| Backup duration | {b['backup']['seconds']} s |
| SHA-256 | `{b['backup']['sha256']}`; re-checked with `sha256sum -c` before restoring |
| gzip integrity | {b['backup']['gzip_integrity']} (`gzip -t`) |
| Restore target | a **fresh** PostgreSQL volume (the previous volume was destroyed first; it held 0 tables) |
| Restore duration | {b['restore']['seconds']} s with the real `infrastructure/scripts/restore.sh` |
| Row counts | **{b['restore']['row_counts']}** in all {b['restore']['tables']} tables ({n(b['restore']['rows'])} rows) |
| Content check | md5 of every ayah's reference and Arabic text identical before and after |
| Ownership / RLS | every table owned by `{b['ownership']['table_owner']}`; that role is not a superuser (`{b['ownership']['app_role_is_superuser']}`), so row-level security applies |
| Migration compatibility | `alembic upgrade head` exits 0 on the restored database |
| Application | API healthy on the restored database; {json.dumps(b['application']['reads'])} |

## Data validation on the restored database

{chr(10).join('- ' + x for x in backup['validation_checks'])}

The two FAIL lines are caused by the verification copy, not by the restore: it holds no tafsir rows and only the published subset of the passages table, so the graph-evidence and registry-count checks cannot match. The same two checks pass on the full development database (14/14).

## Limits (read these before relying on the backups)

{chr(10).join('- ' + x for x in backup['limits'])}
""", encoding="utf-8")

(ROOT / "AI_VERIFICATION_REPORT.md").write_text("""# AI verification report

Date: 2026-10-03. Overall: **PARTIAL**. The platform correctly reports "unavailable" and abstains; generation with a real local model is **BLOCKED** (the model registry is refused by the egress policy).

## Provider

Ollama only (`WOI_AI_MODE=local`, `WOI_EXTERNAL_AI_ENABLED=false`); no paid API is configured or required. The `ollama/ollama:latest` container from `docker-compose.prod.yml` is healthy. `ollama pull` fails because `registry.ollama.ai` is refused by the environment's egress policy (403 on CONNECT; recorded in `data/source-probes.json`). `docker compose exec ollama ollama list` is therefore empty. Model choice for the real host (not tested): with 4 CPUs and 15 GB of RAM and no GPU, an 8B-parameter quantised model is the practical ceiling; a 3B-class model is safer. That is a sizing estimate, not a measurement.

## Pipeline, step by step

| Step | Result | Evidence |
|---|---|---|
| User question | PASS | `POST /api/v1/assistant/query` requires a signed-in user and a CSRF token |
| Classification and safety | PASS_AUTOMATED_ONLY | Questions outside the supported corpora, and unsafe ones, never reach retrieval (tests) |
| Retrieval | PASS | Published, approved passages only (Qur'an text and two translations today); hidden datasets are never searched |
| Source filtering and ranking | PASS | Authority classes kept apart (primary / scholarly / secondary); confidence computed; weak evidence abstains |
| **Ollama** | **BLOCKED** | No model installed. The API returns `ai_synthesis.status = "unavailable"`; the UI says "no local model is running" |
| Citation validation | PASS_AUTOMATED_ONLY | `validate_synthesis` rejects a summary that cites a source not retrieved, or has uncited sentences (tests, with model output supplied by the tests) |
| Answer | PASS | The core answer is verbatim quotation with source, edition, licence and rights status; nothing is paraphrased by a model |
| Uncertainty / abstention | PASS | "Insufficient verified sources" for questions with no support; verified in a real browser on the production stack |

## What the AI is not allowed to do

It never supplies Qur'an quotations, hadith, hadith grades, fiqh rulings, scholar quotations or citations: every quoted item is copied from the database record it cites, and the optional model summary is shown only if every sentence validates against those records; otherwise it is discarded and reported as rejected. Hadith, gradings, tafsir, fiqh and scholars have **no published data**, so the assistant cannot answer from them at all.

## What the UI now shows

- **SOURCE EVIDENCE**: a heading above the quoted passages.
- **LOCAL AI** and **MODEL: `<name>`** (from configuration) in the AI section, whether or not the model answered. If external AI were ever enabled the label would read EXTERNAL AI.
- The unavailable, rejected and validated states, and the line "It is not itself a source."

Checked in real Chromium on the production stack and in an API test.

## Not tested

Generation, latency and memory of any real model; quality of any summary; behaviour when the model returns malformed or adversarial text beyond what the unit tests cover.
""", encoding="utf-8")
print("wrote WORLD_OF_ISLAM_FINAL_REPORT.md, BACKUP_RESTORE_REPORT.md, AI_VERIFICATION_REPORT.md;", verdict)
