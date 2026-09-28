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

---

# Cloud runtime, remote browser and human verification: acceptance status

Legend: **IMPLEMENTED** code exists · **TESTED** exercised for real in the build environment (real
PostgreSQL, real Chromium, real processes/containers; local fixture pages where a site was needed) ·
**LIVE VERIFIED** done against real third-party services · **PENDING** needs your server/accounts ·
**BLOCKED** cannot be done from the build environment.

No item is LIVE VERIFIED yet: the build environment's egress policy blocks every job site, Telegram
and external SMTP/IMAP servers.

| Question | Status | Evidence |
|---|---|---|
| Continues when the laptop is off? | TESTED (cloud host) · PENDING (your laptop-off test) | The stack ran unattended on a cloud machine with no client attached: scheduled discovery, backoff, daily report, heartbeats. The build environment never involved your laptop, but the explicit laptop-off test (DEPLOYMENT.md §9) must be run on your server |
| Scheduler persistent? | TESTED | Leader advisory lock; all state in PostgreSQL; survived `compose down/up`, Docker daemon restart and a PostgreSQL restart |
| Workers persistent? | TESTED | Restart policy + self-watchdog; SIGKILL → auto-restart; network partition → DEAD → recovery |
| Chromium runs on the server? | TESTED | Chromium 140 launched inside the hardened worker container (uid 1001, CapEff=0, read-only fs) |
| Real Chromium operates remotely; click, type, scroll, upload, dynamic forms? | TESTED (fixtures) · PENDING (real sites) | Browser agent: verified semantic clicks, typing, select, radio/checkbox, file upload, multi-step forms, popup-follow; remote session: tap/click, type, keys, scroll |
| CAPTCHA triggers VERIFICATION_REQUIRED? | TESTED (fixture widget) · PENDING (real providers) | `test_captcha_hold_phone_completes_and_workflow_resumes`, `test_captcha_is_recorded_not_bypassed` |
| Do I receive a notification? | Dashboard TESTED · Email TESTED (local SMTP server) · Telegram TESTED (request format, local endpoint) · real delivery PENDING | `test_email_notification_delivered_over_real_smtp`, `test_telegram_request_and_retry_then_give_up` |
| Can I open the session from my phone? | TESTED (emulated iPhone 13, touch) · PENDING (your phone) | The test logs in on a mobile-emulated Chromium through a real uvicorn server, opens `/verify/<id>`, and receives live frames |
| Can I complete the challenge? | TESTED (fixture) | The phone tap on the streamed frame clicked the widget inside the held page |
| Does automation detect completion? | TESTED | Two consecutive clear checks; "still present" feedback otherwise |
| Does the workflow resume automatically? | TESTED | Event sequence QUEUED→STARTED→VERIFICATION_REQUIRED→STARTED→FORM_COMPLETED→SUBMITTING→SUBMITTED with all 10 preflight checks passing |
| Does the session expire safely? | TESTED | `test_verification_timeout_pauses_safely`: VERIFICATION_TIMEOUT, no submit, notification, retry permitted only because submit was never clicked |
| Duplicate submission prevented? | TESTED | Worker SIGKILLed right after the submit click → UNKNOWN, never re-dispatched, re-queue refused; exactly one request reached the form endpoint |
| Submission evidence recorded? | TESTED (fixture) · PENDING (real employer) | Confirmation text/URL/application ID/screenshot tied to events; CONFIRMATION_EMAIL via IMAP reconciliation (matching tested; live IMAP PENDING) |
| UNKNOWN handled correctly? | TESTED | No confirmation → UNKNOWN; reconciliation by email or explicit human decision (`NOT SUBMITTED` confirmation) |
| Browser sessions protected? | TESTED | Session cookie + Origin check + short-lived HMAC token; forged/expired/other-session tokens rejected; CSP |
| Credentials protected? | TESTED | Vault encryption, write-only UI, redaction (a Telegram-token leak path was found and fixed) |
| Raw Chromium debug interface inaccessible? | TESTED | No debug port exists (pipe transport); verified listening sockets in the running container |
| Recovers from browser crash? | TESTED | Chromium processes SIGKILLed mid-application → re-queued, fresh browser, then SUBMITTED once |
| Recovers from worker crash? | TESTED | Container restart policy, lease reclaim, UNKNOWN after click |
| Survives server restart? | TESTED (Docker daemon restart) · PENDING (a full VM reboot) | All services returned healthy with state intact |
| Reconciles interrupted applications? | TESTED | reclaim_expired + watchdog; restore procedure documented |
| Real discovery / submission on a live platform | BLOCKED here · PENDING on your server | Egress policy; see the live validation sequence above |
| Full `docker compose --profile tls up` with a real domain/certificate | PENDING | Caddy config provided; no public DNS/port 80 in the build environment |

## Failure-recovery drill results (running Docker stack, production mode)

| Drill | Result |
|---|---|
| Cold start (all containers together) | First run: a worker crashed on a platform-registry insert race and was restarted by Docker. **Fixed** (advisory lock); re-run: 0 restarts |
| SIGKILL worker process | Container restarted automatically; heartbeats resumed |
| Network partition of worker (150 s) | Marked DEAD at 120 s and tasks reclaimed. First run: the worker never recovered because a DB socket hung. **Fixed** (TCP keepalive/timeouts + always-on watchdog); re-run: ALIVE 15 s after the network returned |
| PostgreSQL restart | 0 process restarts; all processes reconnected within 60 s |
| Docker daemon restart (server reboot) | All 4 services healthy again automatically; admin, sources and RUNNING state intact |
| Worker SIGKILL after submit click (pytest, real process) | UNKNOWN, single submission, re-queue refused |
| Chromium SIGKILL mid-application (pytest) | Re-queued → fresh Chromium → SUBMITTED once |
| Verification timeout | VERIFICATION_TIMEOUT; no submission; browser closed |
