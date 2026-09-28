# JOB AUTOPILOT — Architecture

This document is the plan the code implements. Anything described here that is
not implemented is explicitly labelled **NOT IMPLEMENTED** or **NOT SUPPORTED**.

## 0. Environment findings (build container, 2026-09-28)

| Item | Finding |
|---|---|
| Languages | Python 3.11, Node 22 |
| Browser automation | Playwright 1.63 (Python) + Chromium 141 at `/opt/pw-browsers` |
| Database | PostgreSQL 16 (local cluster) |
| Queue / locks | Redis 7 available; the system uses PostgreSQL (`FOR UPDATE SKIP LOCKED` + unique constraints) as the queue so that queue state and application state commit in **one transaction** |
| Docker | Docker Engine 29 client present |
| AI provider | No provider key configured → AI status is `NOT CONFIGURED` until you configure one |
| Secret storage | No cloud secret manager reachable. Master key is taken from `JOBAP_MASTER_KEY` or a file (`JOBAP_MASTER_KEY_FILE`, e.g. a Docker/K8s secret) |
| Outbound network | **Blocked by the build container's egress policy** for all job hosts (Greenhouse, Lever, Ashby, LinkedIn, Indeed, Bayt, GulfTalent, Naukrigulf). Live connector validation therefore **could not be performed in the build environment**. It must be performed on the deployment server (see `ACCEPTANCE.md`). |

## 1. Architecture

```
                       ┌────────────────────────────┐
  Admin (phone/browser)│  web  (FastAPI + Jinja2)   │  auth, CSRF, dashboard, admin controls
  ────────────────────▶│  /health  /  /applications │
                       └──────────────┬─────────────┘
                                      │ SQL (same DB)
┌─────────────┐   enqueue    ┌────────▼─────────┐   claim (SKIP LOCKED)  ┌──────────────────┐
│  scheduler  │─────────────▶│   PostgreSQL      │◀──────────────────────│  worker(s)        │
│ (1 process, │  tasks table │  tasks, jobs,     │  results, events,     │  discover / match │
│  leader     │              │  applications,    │  evidence             │  apply (Playwright│
│  advisory   │              │  evidence, audit  │──────────────────────▶│  Chromium)        │
│  lock)      │              └───────────────────┘                       └────────┬─────────┘
└─────────────┘                                                                   │ HTTPS
                                                                      real job APIs / real ATS forms
```

Processes (all the same Docker image, different command):

* `web` – dashboard + JSON API + health.
* `scheduler` – holds a PostgreSQL advisory lock (only one active leader),
  enqueues `discover`, `evaluate`, `apply`, `daily_report` tasks according to
  the settings stored in the DB.
* `worker` – N replicas. Claims tasks with `SELECT … FOR UPDATE SKIP LOCKED`,
  runs them, records the outcome. Browser tasks run in a fresh, isolated
  Playwright browser context per application.

## 2. Technology choices

| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.11 | Playwright, PDF/DOCX parsing, AI SDK-free HTTP clients |
| Web | FastAPI + server-rendered Jinja2 (no JS framework, no CDN) | small attack surface, CSP `default-src 'self'` |
| ORM | SQLAlchemy 2 | parameterised queries only (SQLi protection) |
| DB | PostgreSQL 16 | transactions, `SKIP LOCKED`, advisory locks, JSONB |
| Queue | `tasks` table in PostgreSQL | exactly-once state transitions are committed with the task |
| Browser | Playwright + Chromium, stock configuration | **no** stealth plugins, **no** fingerprint spoofing |
| Crypto | `cryptography` AES-256-GCM envelope encryption | authenticated encryption, per-record data keys, key IDs for rotation |
| Passwords (admin) | `hashlib.scrypt` | memory-hard KDF from stdlib |
| CV parsing | `pypdf`, `python-docx` | deterministic text extraction |
| AI | pluggable: `none` (default), `anthropic`, `openai`, `ollama` over plain HTTPS | no hardcoded provider; profile data is only sent when you enable it |

## 3. Database schema (PostgreSQL)

All tables are in `autopilot/models.py`. Core ones:

* `users` – admin accounts (scrypt hash).
* `web_sessions` – server-side sessions (token stored as SHA-256 hash), CSRF token.
* `candidate_profiles` – one per user; editable preferences & rules (JSON validated by pydantic).
* `candidate_facts` – **source-of-truth facts**: `key`, `value`, `category`,
  `status ∈ {VERIFIED, INFERRED, UNKNOWN, NOT_APPLICABLE, CONFLICT}`,
  `source ∈ {USER, CV:<version>, PREVIOUS_ANSWER:<id>}`, `source_excerpt`.
* `cv_versions` – filename, sha256, size, mime, storage path (outside web root, encrypted at rest), `is_active`.
* `credentials` – platform, username, `ciphertext`, `nonce`, `wrapped_key`, `key_id`, `rotate_after`. Never returned by the API.
* `platforms` – static registry + user status: `CONNECTED`, `LOGIN_FAILED`, `VERIFICATION_REQUIRED`, `NOT_CONFIGURED`, `NOT_AUTOMATABLE`, `NO_LOGIN_REQUIRED`.
* `platform_sessions` – encrypted Playwright storage state per platform (cookies are secrets → encrypted).
* `job_sources` – what to search: connector + board token / company slug + filters.
* `jobs` – normalised job; `UNKNOWN` fields stay NULL and are rendered as UNKNOWN; `fingerprint`, `duplicate_of_id`.
* `job_matches` – per-criterion analysis (JSON) + score + decision + reasons.
* `applications` – state machine (see §5); unique `(job_id, mode)`; `cv_version_id`; `retry_count`; `external_application_id`.
* `application_questions` / `application_answers` – question text, field type, answer, provenance JSON, validation result.
* `application_events` – timestamped state transitions & browser events.
* `application_evidence` – `kind ∈ {CONFIRMATION_URL, CONFIRMATION_TEXT, SCREENSHOT, APPLICATION_ID, PLATFORM_RESPONSE}`; always linked to an `application_event`.
* `errors`, `reports`, `system_events`, `audit_log`, `tasks`, `worker_heartbeats`, `settings`.

## 4. Security model

* **Credentials** – AES-256-GCM. Each secret is encrypted with a random 256-bit data
  key; the data key is wrapped with the master key (key ID stored). Rotating the
  master key re-wraps data keys (`autopilot rotate-master-key`). Decryption happens
  only inside the worker (`CredentialVault.use()` context manager) at the moment a
  login form is filled.
* **No plaintext** – the API/dashboard only ever show `username`, `last_tested`,
  `status`. The password field is write-only.
* **Logging** – every log record passes through `RedactingFilter`, which removes
  registered secret values and anything that looks like a password/token/cookie field.
  Playwright traces are **disabled** (they would record typed passwords).
* **Web** – login required for every page, server-side sessions,
  `HttpOnly; Secure; SameSite=Strict` cookies, per-session CSRF token on every
  POST, strict CSP, Jinja2 autoescaping (XSS), login rate limiting, upload size &
  type checks.
* **Files** – CVs are stored under `JOBAP_DATA_DIR/files` (not served statically),
  encrypted at rest with the vault, downloaded only through an authenticated route.
* **Privacy** – the AI provider receives candidate data only when
  `ai.allow_candidate_data = true` is set by you. Data export (`/profile/export`) and
  deletion (`/profile/delete`) are provided.
* **Security mechanisms are never bypassed** – CAPTCHA / MFA / OTP / identity checks
  are detected and recorded as `VERIFICATION_REQUIRED`; the worker then moves on.

## 5. Application state machine (atomic transitions)

```
DISCOVERED → EVALUATED → QUEUED → STARTED → FORM_COMPLETED → SUBMITTING → SUBMITTED → VERIFIED
                  │           │        │            │               │
                  ├→ SKIPPED  │        ├→ VERIFICATION_REQUIRED     ├→ UNKNOWN (no evidence)
                  └→ REVIEW   │        ├→ NEEDS_REVIEW (unknown mandatory answers)
                              │        └→ FAILED
                              └→ DRY_RUN_COMPLETE (dry-run only, never SUBMITTED)
```

* Transitions are validated by `autopilot/state.py`; illegal transitions raise.
* `SUBMITTED` requires ≥1 evidence row in the same transaction.
* Once `SUBMITTING` has been entered, the application is **never automatically
  retried** – a crash there leads to `UNKNOWN` for human investigation.

## 6. Worker architecture

* Task types: `discover(source_id)`, `evaluate(job_id)`, `apply(application_id)`, `daily_report(date)`.
* Claiming: `UPDATE tasks SET status='RUNNING', locked_by=…, locked_until=now()+lease
  WHERE id = (SELECT id FROM tasks WHERE status='PENDING' AND run_after<=now()
  ORDER BY priority, id FOR UPDATE SKIP LOCKED LIMIT 1)`.
* Leases expire; a crashed worker's task is re-queued **unless** it is an `apply`
  task whose application reached `SUBMITTING` (→ `UNKNOWN`).
* Double-submit protection: (1) unique `(job_id, mode)` on applications,
  (2) duplicate-job linking, (3) row lock on the application during apply,
  (4) `SUBMITTING` is terminal for automatic retries.
* Retry with exponential backoff + jitter for transient errors; per-host token-bucket
  rate limiter persisted in the DB; daily/per-platform caps checked in the same
  transaction that queues an application.

## 7. Platform integration strategy

See `PLATFORMS.md` for the per-platform assessment. Summary:

| Platform | Discovery | Apply | Status |
|---|---|---|---|
| Greenhouse (employer boards) | Official public Job Board API | Hosted public application form (Playwright) | SUPPORTED – needs live validation |
| Lever (employer boards) | Official public Postings API | Hosted public application form (Playwright) | SUPPORTED – needs live validation |
| Ashby (employer boards) | Official public Posting API | Hosted public application form (Playwright) | SUPPORTED – needs live validation |
| Generic employer portal with login | — | Login test via configured selectors | LOGIN TEST ONLY |
| LinkedIn | — | — | NOT AUTOMATABLE (User Agreement prohibits bots/automated access) |
| Indeed | — | — | NOT AUTOMATABLE (ToS prohibits automated access; no applicant API) |
| Bayt / GulfTalent / Naukrigulf | — | — | NOT AUTOMATABLE (terms prohibit automated access; no public applicant API) |

## 8. Deployment architecture

`docker-compose.yml` runs `postgres`, `web`, `scheduler`, `worker` (scalable).
On a VPS/cloud VM this runs continuously independent of your laptop. TLS is terminated
by a reverse proxy (Caddy/nginx, documented in `DEPLOYMENT.md`). The master key is
provided as a Docker secret file.

## 9. Implementation roadmap (phases → modules)

| Phase | Module(s) |
|---|---|
| 1 Architecture/repo | this doc, `pyproject.toml`, Docker |
| 2 DB & profile | `models.py`, `db.py`, `profile/` |
| 3 Vault | `security/vault.py`, `security/redact.py` |
| 4 CV & knowledge | `profile/cv_parser.py`, `profile/knowledge.py` |
| 5 Q&A & grounding | `questions/`, `ai/` |
| 6 Discovery | `connectors/greenhouse.py`, `lever.py`, `ashby.py` |
| 7 Matching & dedup | `jobs/` |
| 8 Browser framework | `browser/` |
| 9–10 First connector + submission | `connectors/*_apply.py`, `browser/submit.py` |
| 11 Evidence & audit | `evidence.py`, `audit.py` |
| 12 Scheduler & workers | `workers/` |
| 13 Reports | `reports.py` |
| 14 Dashboard | `web/` |
| 15 More connectors | registry entries (+ NOT AUTOMATABLE records) |
| 16 Deployment | `docker-compose.yml`, `docs/DEPLOYMENT.md` |
