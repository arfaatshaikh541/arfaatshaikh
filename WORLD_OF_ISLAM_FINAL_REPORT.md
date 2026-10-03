NOT_PRODUCTION_READY

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

1. MinIO [BLOCKED]: quay.io/minio/minio:RELEASE.2025-07-23T15-54-02Z cannot be pulled: quay.io is refused by the environment's egress policy (403 on CONNECT); re-tried 2026-10-03.
2. MinIO init [BLOCKED]: quay.io/minio/mc:RELEASE.2025-07-21T05-28-08Z cannot be pulled for the same reason. Bucket creation, upload, download, checksum storage and backup storage in MinIO are NOT_TESTED.
3. Ollama [PARTIAL]: ollama/ollama:latest container healthy. No model is installed: registry.ollama.ai is refused by the egress policy. The API reports ai_synthesis.status = unavailable and still returns quoted, cited evidence; real generation is NOT_TESTED.
4. Backup [PARTIAL]: The real backup service wrote a 72,817,232-byte gzip of a populated 397 MB database in 30 s; checksum recorded; gzip integrity checked. The design writes to ./backups only: nothing is stored in MinIO, and an off-machine copy is NOT_TESTED.
5. Real domain [BLOCKED]: https://app.arfaat.com/worldofislam is refused by the egress policy from this environment (403 on CONNECT), and the certificate in /etc/letsencrypt is the self-signed one created for the test; every browser check used a local hosts mapping.
6. TLS on the real domain [NOT_TESTED]: No public certificate was obtained or tested.
7. Object storage [BLOCKED]: MinIO could not be started (above); the API's /health/ready reports object_storage=false (degraded).
8. Published data has a documented rights status [PARTIAL]: Every published dataset has a ledger entry, but the four published Qur'an datasets and the mosque data are PUBLISH_WITH_CAVEAT, not established rights.
9. Religious content is source-backed [PARTIAL]: The Qur'an text and two translations are shown with source and licence, but their rights are caveated; hadith, hadith grades and tafsir are hidden; fiqh, aqeedah, seerah and scholars have no data.

## 3. Network probe (Priority 1)

Run from this VM on 2026-10-03 with `scripts/probe_sources.py` (62 targets: 2 accessible, 5 with reachable data). Full records, including robots.txt and rights notes for all targets, are in [`data/source-probes.json`](data/source-probes.json).

| Source | Host | DNS | TLS | HTTP | Licence page | Terms page | Data | Last checked (UTC) | Result |
|---|---|---|---|---|---|---|---|---|---|
| Wikidata | www.wikidata.org | ok | - | - | False | False | False | 2026-10-03T16:55 | BLOCKED by egress policy (403 on CONNECT) |
| OpenStreetMap / Overpass | overpass-api.de | ok | - | - | False | False | False | 2026-10-03T16:55 | BLOCKED by egress policy (403 on CONNECT) |
| Open Library | openlibrary.org | ok | - | - | False | False | False | 2026-10-03T16:55 | BLOCKED by egress policy (403 on CONNECT) |
| Internet Archive | archive.org | ok | - | - | False | False | False | 2026-10-03T16:55 | BLOCKED by egress policy (403 on CONNECT) |
| Project Gutenberg | www.gutenberg.org | ok | - | - | False | False | None | 2026-10-03T16:55 | BLOCKED by egress policy (403 on CONNECT) |
| Charity Commission (E&W) | register-of-charities.charitycommission.gov.uk | ok | - | - | False | False | False | 2026-10-03T16:55 | BLOCKED by egress policy (403 on CONNECT) |
| OSCR (Scotland) | www.oscr.org.uk | ok | - | - | False | None | False | 2026-10-03T16:55 | BLOCKED by egress policy (403 on CONNECT) |
| ACNC (Australia) | www.acnc.gov.au | ok | - | - | False | None | False | 2026-10-03T16:55 | BLOCKED by egress policy (403 on CONNECT) |
| Job API: Adzuna | developer.adzuna.com | ok | - | - | False | False | None | 2026-10-03T16:55 | BLOCKED by egress policy (403 on CONNECT) |
| Job API: Arbeitnow | www.arbeitnow.com | ok | - | - | False | False | False | 2026-10-03T16:55 | BLOCKED by egress policy (403 on CONNECT) |
| Recitations: mp3quran | mp3quran.net | ok | - | - | False | False | None | 2026-10-03T16:55 | BLOCKED by egress policy (403 on CONNECT) |
| Recitations: EveryAyah | everyayah.com | ok | - | - | False | False | None | 2026-10-03T16:55 | BLOCKED by egress policy (403 on CONNECT) |
| sunnah.com API | sunnah.com | ok | - | - | False | False | None | 2026-10-03T16:55 | BLOCKED by egress policy (403 on CONNECT) |
| Ollama model registry | registry.ollama.ai | ok | - | - | None | None | False | 2026-10-03T16:55 | BLOCKED by egress policy (403 on CONNECT) |
| quay.io (MinIO images) | quay.io | ok | - | - | None | None | False | 2026-10-03T16:55 | BLOCKED by egress policy (403 on CONNECT) |
| The real URL (app.arfaat.com) | app.arfaat.com | ok | - | - | None | None | None | 2026-10-03T16:55 | BLOCKED by egress policy (403 on CONNECT) |
| Docker Hub registry | registry-1.docker.io | ok | - | 401 | None | None | None | 2026-10-03T16:55 | HTTP 401 Unauthorized |
| PyPI | pypi.org | ok | - | 200 | False | None | True | 2026-10-03T16:55 | REACHABLE |
| npm registry | registry.npmjs.org | ok | - | 200 | False | None | False | 2026-10-03T16:55 | REACHABLE |

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
| Database | PostgreSQL 17.11, revision 20261003_0088, 397,170,355 bytes, 369 tables, 543,946 rows (populated copy) |
| Backup | `woi-20261003T161342Z.sql.gz`, 72,817,232 bytes, 30 s, gzip integrity ok |
| SHA-256 | `96a4661d9416ed2df2c2179de37b3b0f70d1c26b16b1fccac13bab183b69c019` (verified again before the restore) |
| Restore into a fresh volume | 22 s with the real `restore.sh`; row counts **identical** in all 369 tables; Qur'an text hash identical |
| Migrations on the restored database | `alembic upgrade head` exits 0 |
| Validation | 12 of 14 pass; the two failures come from the disk-limited copy (no tafsir rows), and the same checks pass 14/14 on the full database |
| Application | API healthy on the restored database; reads return 114 surahs and 19,776 visible mosque listings |
| MinIO storage / download of backups | **BLOCKED / NOT_TESTED** |

## 7. Security (Priority 13): AUTOMATED_SECURITY_TESTED

**Label: AUTOMATED_SECURITY_TESTED.** Everything below is an automated check run by the team that wrote the code. It is not a penetration test and must not be described as one.

| Check | Result | How |
|---|---|---|
| Python dependencies | PASS_AUTOMATED_ONLY | `pip-audit` on the 162 locked production packages (`uv export --frozen --no-dev`): no known vulnerabilities |
| JavaScript dependencies | PASS_AUTOMATED_ONLY | `pnpm audit --prod`: no known vulnerabilities |
| Secrets | PASS_AUTOMATED_ONLY | `detect-secrets` over tracked files: 15 files with hits, all documentation placeholders, test fixtures or UI labels; regex for private keys and provider tokens: none; no `.env`, `.pem` or `.key` file is tracked; a Redis dump that was tracked is now untracked and ignored |
| CORS | PASS_AUTOMATED_ONLY | An unlisted origin receives no `Access-Control-Allow-Origin`; the listed origin does; preflight from an unlisted origin is refused |
| CSRF | PASS_AUTOMATED_ONLY | State-changing requests without the token are refused (403), including the new review sync |
| Authentication | PASS_AUTOMATED_ONLY | Wrong password refused without saying which part; session cookie `HttpOnly`, `Secure`, scoped to `/worldofislam`; logout ends the session |
| Authorisation | PASS_AUTOMATED_ONLY | Anonymous 401 and non-administrator 403 on the admin API, the review queues and the new Arabic review CSV export; an administrator receives the CSV |
| Rate limits | PASS_AUTOMATED_ONLY | Repeated logins return 429 (application limiter and nginx zone) |
| Upload limits | PASS_AUTOMATED_ONLY | Malformed JSON bodies 422; a 33 MB body 413 (nginx `client_max_body_size 10m`) |
| SSRF | PASS_AUTOMATED_ONLY | Importer downloads are limited to an HTTPS host allowlist and redirects are re-checked (9 tests) |
| XSS | PASS_AUTOMATED_ONLY | Markup in a display name and in a query string is rendered as text and not executed (real Chromium); CSP `default-src 'self'`, `frame-ancestors 'none'` |
| SQL injection | PASS_AUTOMATED_ONLY | Injection-style input to the directory, search and knowledge endpoints never produced a server error; the database was intact afterwards |
| CSV export | PASS_AUTOMATED_ONLY | Cells starting with `=`, `+`, `-`, `@` are prefixed so a spreadsheet cannot run them as formulas |
| Transport | PASS_AUTOMATED_ONLY | HSTS, nosniff, referrer policy, permissions policy sent once each; no `Server` version, no `X-Powered-By`; API docs/OpenAPI return 404 in production; only nginx publishes ports 80/443 |
| Real host | NOT_TESTED | The real domain is unreachable from the build VM |
| DoS / WAF / independent penetration test | NOT_TESTED | Not performed |

No independent penetration test took place. DoS, WAF and the real host were not tested.

## 8. AI (Priority 4)

Full account: [`AI_VERIFICATION_REPORT.md`](AI_VERIFICATION_REPORT.md). In short: the Ollama service runs; **no model could be installed**; the platform says so (LOCAL AI, model name, "no local model is running") and still returns quoted, cited evidence; with no sufficient source it abstains. The model-dependent path (retrieval, source filtering, **Ollama**, citation validation) is **NOT_TESTED** with a real model; citation validation is tested against model output supplied by tests (fabricated citations are rejected).

## 9. Production verification run (2026-10-03)

Stack: the real `docker-compose.prod.yml` on this VM with MinIO disabled (the only deviations are listed in [`data/verification-prod-compose.json`](data/verification-prod-compose.json)). Real Chromium against `https://app.arfaat.com/worldofislam` **through a hosts mapping and a self-signed certificate** (not the real domain): `browser-verify.cjs` 61 passed / 0 failed; `prod-extra-verify.cjs` 47 passed / 0 failed. Every failure observed during the phase is recorded in section 11.

| Component / criterion | Result | Evidence | Tested on |
|---|---|---|---|
| PostgreSQL | **PASS** | postgres:17-alpine from docker-compose.prod.yml; healthy; the application role is not a superuser and owns the tables (row-level security applies); restored from backup. | build VM (not the production host) |
| Redis | **PASS** | redis:8-alpine healthy; used by the rate limiter and as the Celery broker. | build VM (not the production host) |
| API | **PASS** | Built from apps/api/Dockerfile; healthy; 780 API tests pass. | build VM (not the production host) |
| Web | **PASS** | Built from apps/web/Dockerfile; 61 + 47 real-Chromium checks passed (English, Arabic RTL, mobile, admin, assistant, PWA, offline, security headers). | build VM (not the production host) |
| nginx | **PASS_AUTOMATED_ONLY** | nginx:1.27-alpine with infrastructure/nginx/woi.conf.template; TLS with a SELF-SIGNED certificate; security headers, rate limits and the 10 MB body limit checked. Not tested with a public certificate. | build VM (not the production host) |
| MinIO | **BLOCKED** | quay.io/minio/minio:RELEASE.2025-07-23T15-54-02Z cannot be pulled: quay.io is refused by the environment's egress policy (403 on CONNECT); re-tried 2026-10-03. | build VM (not the production host) |
| MinIO init | **BLOCKED** | quay.io/minio/mc:RELEASE.2025-07-21T05-28-08Z cannot be pulled for the same reason. Bucket creation, upload, download, checksum storage and backup storage in MinIO are NOT_TESTED. | build VM (not the production host) |
| Ollama | **PARTIAL** | ollama/ollama:latest container healthy. No model is installed: registry.ollama.ai is refused by the egress policy. The API reports ai_synthesis.status = unavailable and still returns quoted, cited evidence; real generation is NOT_TESTED. | build VM (not the production host) |
| Celery worker | **PASS** | The worker container registers woi.email.send_outbox, woi.auth.purge_expired and woi.data.validate (celery inspect registered) and runs beat; all three ran end to end on a populated database; unit and database tests included. | build VM (not the production host) |
| Backup | **PARTIAL** | The real backup service wrote a 72,817,232-byte gzip of a populated 397 MB database in 30 s; checksum recorded; gzip integrity checked. The design writes to ./backups only: nothing is stored in MinIO, and an off-machine copy is NOT_TESTED. | build VM (not the production host) |
| Migrations | **PASS** | alembic upgrade head exits 0 on the restored database (revision 20261003_0088); the up/down/up cycle passed earlier. | build VM (not the production host) |
| Real domain | **BLOCKED** | https://app.arfaat.com/worldofislam is refused by the egress policy from this environment (403 on CONNECT), and the certificate in /etc/letsencrypt is the self-signed one created for the test; every browser check used a local hosts mapping. | not reachable from the build VM |
| TLS on the real domain | **NOT_TESTED** | No public certificate was obtained or tested. | not reachable from the build VM |
| Database backup and restore | **PASS_AUTOMATED_ONLY** | Restored into a fresh PostgreSQL 17 volume with the real restore.sh in 22 s: row counts identical in all 369 tables (543,946 rows), Qur'an text hash identical, the application started healthy on it. Data validation 12/14; the 2 failures are caused by the disk-limited copy (no tafsir rows), not by the restore. The full 5.5 GB database was not restored. | build VM (not the production host) |
| Object storage | **BLOCKED** | MinIO could not be started (above); the API's /health/ready reports object_storage=false (degraded). | build VM (not the production host) |
| AI works or reports unavailable | **PASS** | With no model the API and UI say so (LOCAL AI, the model name, 'no local model is running') and the quoted evidence still appears; with no sources the assistant abstains. | build VM (not the production host) |
| No fake data | **PASS_AUTOMATED_ONLY** | Every imported record comes from a named source with a checksum; test fixtures are rolled back; no human has audited this. | build VM (not the production host) |
| Published data has provenance | **PASS** | scripts/validate_data.py 14/14 on the full development database (12/14 on the filtered verification copy; both failures explained above). | build VM (not the production host) |
| Published data has a documented rights status | **PARTIAL** | Every published dataset has a ledger entry, but the four published Qur'an datasets and the mosque data are PUBLISH_WITH_CAVEAT, not established rights. | build VM (not the production host) |
| Geographic coverage is explicit | **PASS** | GET /knowledge/coverage and the status page: mosques ALGERIA_ONLY, COMMUNITY_DATA, NOT_INDIVIDUALLY_VERIFIED. | build VM (not the production host) |
| Religious content is source-backed | **PARTIAL** | The Qur'an text and two translations are shown with source and licence, but their rights are caveated; hadith, hadith grades and tafsir are hidden; fiqh, aqeedah, seerah and scholars have no data. | build VM (not the production host) |
| Email delivery | **PASS_AUTOMATED_ONLY** | The worker sends verification and password-reset mail through SMTP (tested against a local SMTP server, and the emailed token verified an account). No real provider is configured: WOI_SMTP_HOST is empty in .env.production, so no user can currently receive these emails. | build VM (not the production host) |
| Security | **PASS_AUTOMATED_ONLY** | AUTOMATED_SECURITY_TESTED. pip-audit and pnpm audit clean; secret scan clean; CORS, CSRF, authentication, authorisation, rate limit, upload limit, SSRF allowlist, XSS and SQL-injection probes pass. No independent penetration test took place. | build VM (not the production host) |
| Offline | **PASS_AUTOMATED_ONLY** | Visited pages reopen offline (layout only); a downloaded Qur'an is readable and searchable offline; API data, audio and AI are not available offline (by design, or no data). | build VM (not the production host) |
| Arabic review | **BLOCKED** | 168 strings await a native reader and 0 are approved. The reviewer workflow (context, English source, category, status, reviewer, timestamp, attestation, CSV hand-off) is built and tested, but only a person can approve. | build VM (not the production host) |

## 10. Data domains

| Domain | Status | Records | Published | Hidden | Rights decision | Coverage |
|---|---|---:|---:|---:|---|---|
| Qur'an | **RIGHTS_UNVERIFIED** | 6,236 | 6,236 | 0 | PUBLISH_WITH_CAVEAT | GLOBAL |
| Hadith | **RIGHTS_UNVERIFIED** | 15,110 | 0 | 15,110 | KEEP_HIDDEN | HIDDEN_PENDING_RIGHTS |
| Hadith gradings | **RIGHTS_UNVERIFIED** | 21,185 | 0 | 21,185 | KEEP_HIDDEN | HIDDEN_PENDING_RIGHTS |
| Tafsir | **RIGHTS_UNVERIFIED** | 182,320 | 0 | 182,320 | KEEP_HIDDEN | HIDDEN_PENDING_RIGHTS |
| Fiqh | **EMPTY** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Aqeedah | **EMPTY** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Seerah | **EMPTY** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Scholar biographies | **SOURCE_BLOCKED** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Islamic terminology | **EMPTY** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Islamic history | **EMPTY** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Islamic civilization | **EMPTY** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Libraries, books and catalogues | **SOURCE_BLOCKED** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Mosques | **PUBLISHED** | 19,781 | 19,776 | 5 | PUBLISH_WITH_CAVEAT | ALGERIA_ONLY |
| Organisations | **EMPTY** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Events | **EMPTY** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Charities | **SOURCE_BLOCKED** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Volunteering | **EMPTY** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Businesses | **EMPTY** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Professionals | **EMPTY** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Health services | **EMPTY** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Jobs | **SOURCE_BLOCKED** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |
| Recitation audio | **SOURCE_BLOCKED** | 0 | 0 | 0 | no dataset | NO_VERIFIED_DATA |

No domain is READY. No data was added in this phase; no hidden dataset was published or deleted.

## 11. Failures and defects found and fixed in this phase

- Email delivery did not exist: verification and password-reset mail was queued in email_outbox and nothing ever sent it, so no user could verify an address or reset a password. Fixed with the woi.email.send_outbox task; still needs SMTP settings on the host.
- The worker registered no tasks. Fixed: three real tasks (mail, purge, validation) with retry, idempotency, logging and tests.
- Re-syncing the Arabic review queue overwrote the whole payload and erased a reviewer's recorded suggested text. Fixed (merge instead of replace) and tested.
- The tajweed credit shown to readers named 'quran.ws' and did not match the licence file (Quranpedia, with a prescribed credit line and licence link). Fixed.
- The assistant UI did not name the model, did not say LOCAL AI, and did not label the quoted passages SOURCE EVIDENCE; the early-abstention response omitted the AI identity block. Fixed and tested.
- Coverage said ALGERIA_ONLY but did not carry COMMUNITY_DATA or NOT_INDIVIDUALLY_VERIFIED. Fixed (derived from live verification counts).
- infrastructure/verify/prod-compose.sh generated invalid YAML (a repeated 'api' key). Fixed.
- backup-restore.sh first reported 'validation passed 0 failed 0' when the validator had actually failed to connect (the backend network is internal, so a host-side client cannot reach the database). Caught, the script now runs the validator inside the stack network and fails loudly if it produces no result.
- My own mistake: restore.sh was first pointed at 'the newest file' in ./backups, which was an empty-database backup written by the new stack's backup service at start-up. Caught by the row-count check and redone with the intended file; documented in docs/OPERATIONS.md.
- A new API integration test failed in a full run because the application's database engine is created once per process and a second module has its own event loop; moved into the existing integration module.
- Docker Hub answered 429 (rate limit) to base-image lookups for node:22-alpine and python:3.12-slim during rebuilds; retried with spacing.
- An earlier browser run exercised a web image that had not been rebuilt, so the new UI checks failed; the web image was rebuilt and the suites re-run.

## 12. Known limitations

- Rights reasoning is mine from the cited sources; no lawyer reviewed it. No scholar reviewed any religious content. No native reader approved any Arabic string. None of this is fabricated or implied.
- Test counts: API 789 passed, web 43 passed (43), typecheck and ESLint clean.
- `/patch_reports.py` is an empty file I created by mistake in the filesystem root of this VM; it could not be removed from here and is not part of the repository.

## 13. Next actions (in order)

1. Run this repository on the **deployment host** with the compose file unmodified: `docker pull` the two quay.io images, `docker compose exec ollama ollama pull <model>`, then `infrastructure/verify/backup-restore.sh`, `browser-verify.cjs` and `prod-extra-verify.cjs` against `https://app.arfaat.com/worldofislam`, and `scripts/probe_sources.py`.
2. Set `WOI_SMTP_*` so users can verify email and reset passwords.
3. Decide the rights questions (Qur'an text publisher, hadith editions, grading works, tafsir editions, ODbL share-alike for mosques); a native Arabic reader works the 168 strings in "Human review".
4. Only then import further domains, reading each source's licence and terms first.
