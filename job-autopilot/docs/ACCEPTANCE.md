# Acceptance status

Legend:
* **VERIFIED**: exercised for real in the build environment (real PostgreSQL 16, real Chromium,
  real processes) by automated tests or process runs.
* **VERIFIED (fixture)**: our code ran for real, but against local HTML fixture pages, not a
  real platform.
* **PENDING LIVE**: cannot be verified from the build environment, whose egress policy blocks
  every job site. It must be validated on your server with your real accounts and data.

The project is **not complete** until every PENDING LIVE item has been validated.

| # | Item | Status | Evidence / how to validate |
|---|---|---|---|
| 1 | Real database works | VERIFIED | 59 tests run against PostgreSQL 16; the scheduler, worker and web processes ran against it |
| 2 | Real authentication works (dashboard) | VERIFIED | `tests/test_web.py`: login, lockout after 5 failures, server-side sessions, CSRF enforced |
| 3 | Real credential storage works | VERIFIED | `tests/test_security.py`: AES-256-GCM envelope, record binding, tamper detection, key rotation, write-only API |
| 4 | Real CV upload works | VERIFIED | Upload via web, stored encrypted, byte-identical download, versioning, parse to EXTRACTED facts |
| 5 | Real job discovery works | **PENDING LIVE** | Parsers tested against the documented API shapes. A live request to `boards-api.greenhouse.io` was attempted and blocked by the build proxy; the system recorded the error, retried with backoff and showed 0 jobs. **On your server:** add a Greenhouse board, press RUN JOB SEARCH NOW, confirm jobs appear with the source's `last_success_at` set |
| 6 | Real job parsing works | VERIFIED (shapes) / **PENDING LIVE** | Same as 5 |
| 7 | Real matching works | VERIFIED | `tests/test_jobs.py`: transparent per-criterion analysis, rules, thresholds, exclusions |
| 8 | Real browser automation works | VERIFIED (fixture) | Real Chromium, in the container as well, driving real DOM forms |
| 9 | Real form filling works | VERIFIED (fixture) | Text, email, select, radio, file upload; values read back after filling |
| 10 | Real CV upload to application works | VERIFIED (fixture) | The fixture server received the CV filename in the submission |
| 11 | Questions answered from verified data only | VERIFIED | UNKNOWN never becomes YES; academic ≠ professional; conflicts flagged; the grounding validator rejects invented numbers, names and skills |
| 12 | Real submission on ≥1 supported platform | **PENDING LIVE** | Run DRY_RUN on a real Greenhouse job first and inspect the pre-submit screenshot and answers; then switch to LIVE and submit one application to a job you actually want |
| 13 | Submission confirmation detected | VERIFIED (fixture) / **PENDING LIVE** | Confirmation text, URL and application ID extraction verified on the fixture; validate on a real board |
| 14 | Application is recorded | VERIFIED | Full event timeline QUEUED→STARTED→FORM_COMPLETED→SUBMITTING→SUBMITTED |
| 15 | Evidence is stored | VERIFIED | Confirmation text, URL, application ID, encrypted screenshots, each tied to an event. SUBMITTED is impossible without proof-type evidence |
| 16 | Duplicate protection works | VERIFIED | Unique (job, mode); cross-platform fingerprint dedup; concurrent claim test (1 of 5 workers wins); never re-run after SUBMITTING |
| 17 | Error recovery works | VERIFIED | Transient retry with backoff; lease reclaim; crash mid-submit → UNKNOWN (not retried); browser restart on crash; graceful SIGTERM |
| 18 | Scheduler works | VERIFIED | Leader lock, interval discovery, limits, allowed hours, daily report fired at the configured time in a real run |
| 19 | Daily report uses database values | VERIFIED | `tests/test_workers.py::test_report_counts_come_from_db_and_separate_modes`; real scheduled report showed all zeros on an empty DB |
| 20 | Dashboard displays actual values | VERIFIED | Zero state renders 0 and NOT CONFIGURED; health from heartbeats and real checks |
| 21 | Credentials never appear in logs | VERIFIED | Redaction tests; grep of real process logs found no admin password, master key or session cookie |
| 22 | No fake data in production mode | VERIFIED | No seed data; the only static rows are the platform registry. Dry-run is stored and reported separately |
| — | Live login test on a real employer portal | **PENDING LIVE** | Configure the portal on the Platforms page, store the credential, press TEST LOGIN |
| — | AI provider connectivity | **PENDING LIVE** | No provider key was available in the build environment. Configure one and press TEST AI CONNECTION |
| — | Full `docker compose up` | **PENDING LIVE** | Image built and run; compose file validated; Docker Hub was rate-limited for the postgres image in the build environment |

## Recommended live validation sequence

1. Deploy (`DEPLOYMENT.md`), create the admin, upload your CV, verify your facts, set preferences.
2. Add one Greenhouse board you care about → RUN JOB SEARCH NOW → confirm real jobs (item 5).
3. Leave mode = DRY_RUN → START. Open 2–3 `DRY_RUN_COMPLETE` applications. Check every answer's
   provenance and the pre-submit screenshot (items 8–11).
4. Fix any `NEEDS_REVIEW` reasons by adding verified facts.
5. Switch to LIVE, set `max_applications_per_day` to 1, and let it submit one application.
   Confirm the confirmation evidence matches the employer's email (items 12–15).
6. Only then raise the limits.
