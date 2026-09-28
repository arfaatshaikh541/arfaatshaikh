# 24/7 cloud runtime, remote browser and human verification

This extends the existing architecture (`ARCHITECTURE.md`) in place. The same PostgreSQL queue,
leader-locked scheduler, state machine and workers are used. No parallel system was added.

```
                       CLOUD SERVER (docker compose, restart: unless-stopped)
 ┌──────────┐   https   ┌───────┐        ┌─────────────────────────┐
 │  phone   │──────────▶│ caddy │───────▶│ web (FastAPI)           │◀── session cookie + CSRF + Origin
 └──────────┘  wss      └───────┘        │  /verify/<id>/ws relay  │
                                         └───────────┬─────────────┘
                                   internal network  │ ws://worker:9310/session/<id>?t=<HMAC token, 120 s>
 ┌───────────┐   tasks (SKIP LOCKED)  ┌──────────────▼──────────────┐
 │ scheduler │───────────────────────▶│ worker × N                  │── Chromium (Playwright pipe, no debug port)
 │ + watchdog│   PostgreSQL (state)   │  keeper: lease + heartbeat  │── session server (holds 1 page for you)
 └───────────┘◀──────────────────────▶│  self-watchdog → exit/restart│
                                       └─────────────────────────────┘
```

## What runs where

| Service | Role | Persistence |
|---|---|---|
| `postgres` | All state: jobs, applications, events, evidence metadata, tasks, heartbeats, verification requests, notifications, settings | volume `pgdata` |
| `web` | Dashboard, admin controls, verification relay, `/metrics`, `/healthz` | stateless |
| `scheduler` | One leader (advisory lock): discovery schedule, dispatch, daily report, notification retries, email reconciliation, watchdog | stateless |
| `worker` (×N) | Discovery, evaluation, Chromium applications, login tests, notification delivery, reconciliation | stateless; encrypted files in volume `appdata` |
| `caddy` (optional) | TLS (Let's Encrypt) + WebSocket proxy | volume `caddy_data` |

All critical state is in PostgreSQL. Any container can be killed at any moment; see "Recovery" below.

## Human verification flow

1. The worker detects a *visible, interactive* challenge (CAPTCHA frame, OTP/MFA prompt) at any step:
   on page load, on a later form step, before submit, or **after** the submit click.
2. In one transaction: the application moves to `VERIFICATION_REQUIRED`, a `verification_requests` row
   records (application, platform, user, worker, browser session, internal endpoint, kind, **stage**,
   page URL, expiry), a critical dashboard notification is created, and deliveries are queued on every
   configured channel. A challenge screenshot is stored as evidence.
3. The worker stops automating and holds the page. It sends email/Telegram immediately; failures
   are retried by the scheduler every `notification_retry_minutes`, up to `max_notification_attempts`.
4. You open the link (`/verify/<id>`) on your phone and log in. The page streams JPEG frames of the held
   page over an authenticated WebSocket. You tap and type on it yourself: the input is applied by the
   worker to that page only.
5. Every 1.5 s, and immediately when you tap **DONE**, the worker re-inspects the page. It resumes only
   when the challenge is absent (or the page's own CAPTCHA response field is filled) **on two
   consecutive checks**. If it is still there you are told so, and nothing is clicked.
6. On completion the application returns to the interrupted step (`STARTED`, `FORM_COMPLETED`, or
   `SUBMITTING` for a post-submit challenge) and continues. A post-submit challenge only observes
   the outcome afterwards; the submit button is **never clicked twice**.
7. If the request expires (`verification_timeout_minutes`, capped by `browser_session_timeout_minutes`),
   is cancelled, or the worker dies: `VERIFICATION_TIMEOUT` (or `UNKNOWN` if submit had been clicked).
   The browser is closed. There are no reloads, no re-submits, and no success claims.

While one application is held, the scheduler can dispatch the next application to another worker
(`max_open_verification_sessions`, default 2).

## Submission safety

Before the final click, all ten checks must pass (they are recorded in the `preflight` event):

1. intended application in `FORM_COMPLETED`
2. employer
3. job title present on the page
4. destination host unchanged and allowed by the environment policy
5. required fields have values (read back from the DOM)
6. CV attached if the form accepts one
7. every required answer is grounded
8. no visible validation errors
9. this is the final step (a verified, unambiguous submit control; no Next/Continue left)
10. not already submitted or clicked for this job

`FORM_COMPLETED → SUBMITTING` commits `submit_clicked_at` **before** the click. From then on the state
machine refuses any re-queue until a human (or the IMAP reconciler) resolves it. This is the
duplicate-submission guarantee; it was tested by SIGKILLing a worker right after the click.

## Reconciliation of uncertain submissions

`UNKNOWN` and post-click `VERIFICATION_TIMEOUT` applications are reconciled by:

* **Email (implemented):** read-only IMAPS search (`BODY.PEEK`, nothing is marked read) for a message
  that arrived after the click, names the employer, and contains confirmation wording. On a match:
  `CONFIRMATION_EMAIL` evidence and `SUBMITTED`.
* **Human:** paste the confirmation into *Confirm submitted*, or type `NOT SUBMITTED` to reconcile it
  as not received (only then can it be retried).
* **ATS applicant history:** NOT AVAILABLE. Greenhouse, Lever and Ashby hosted forms have no applicant login.

## Notifications

| Channel | Status | Configure |
|---|---|---|
| Dashboard | Always on | — |
| Email (SMTP, STARTTLS/SSL) | Implemented, tested against a local SMTP server | Settings → Notifications; secret `notify:smtp` |
| Telegram Bot API | Implemented, request format tested locally; **live Telegram not tested** (egress blocked) | Settings; secret `notify:telegram` (bot token); chat id |
| Web Push / WhatsApp | NOT IMPLEMENTED | — |

Set `JOBAP_PUBLIC_BASE_URL` so notifications contain a clickable `https://…/verify/<id>` link.

## New environment variables

| Variable | Default | Purpose |
|---|---|---|
| `JOBAP_ENVIRONMENT` | `development` (`production` in compose) | `production` = real submissions to public hosts only; `test` = local fixtures only; `development` = LIVE refused |
| `JOBAP_PUBLIC_BASE_URL` | empty | Absolute links in notifications |
| `JOBAP_DOMAIN` | empty | Domain Caddy obtains a certificate for |
| `JOBAP_SESSION_SERVER_PORT` | `9310` | Worker's internal remote-session port (never publish it) |
| `JOBAP_SESSION_BIND_HOST` / `JOBAP_SESSION_ADVERTISE_HOST` | `0.0.0.0` / container IP | Bind address and the address the web relay uses |
| `JOBAP_TASK_LEASE_SECONDS` | `300` | Crash-detection delay (leases are renewed every 20 s while alive) |
| `JOBAP_WATCHDOG_STALL_SECONDS` | `1800` | A busy worker exits (and is restarted) if it makes no progress for this long; idle limit 300 s |
| `JOBAP_METRICS_TOKEN_FILE` | empty | Bearer token file for `GET /metrics` (Prometheus) |
| `JOBAP_HEARTBEAT_FILE` | `/tmp/jobap-heartbeat` | Liveness file used by the container HEALTHCHECK |

Dashboard settings (Automation page): `hold_for_verification`, `verification_timeout_minutes`,
`browser_session_timeout_minutes`, `max_open_verification_sessions`, `notification_retry_minutes`,
`max_notification_attempts`, `application_timeout_minutes`.

## Platform capability matrix

Each platform row stores explicit states for DISCOVERY, JOB_DETAILS, APPLICATION_REDIRECT,
DIRECT_APPLICATION, AUTOMATED_SUBMISSION and OFFICIAL_API (see the Platforms page):

* Greenhouse, Lever, Ashby: all PENDING_LIVE (implemented, not yet run against the live services)
* SmartRecruiters: DISCOVERY PENDING_LIVE; applying NOT_IMPLEMENTED (jobs are listed for manual application)
* Workable, iCIMS, Workday, Oracle Recruiting, SAP SuccessFactors: NOT_IMPLEMENTED (no official applicant API)
* LinkedIn, Indeed, Bayt, GulfTalent, Naukrigulf: NOT_PERMITTED (their terms prohibit automated use)

## Recovery behaviour (tested)

| Failure | What happens |
|---|---|
| Worker process killed (SIGKILL) | Docker restarts it. The lease expires; the scheduler reclaims the task. Before submit: re-queued. After the click: `UNKNOWN` and never re-dispatched |
| Worker hung (e.g. dead socket) | Self-watchdog exits the process, then restart. DB sockets use TCP keepalive/`tcp_user_timeout` so hangs are bounded |
| Browser crash | Page `crash` event / closed target → pre-submit transient → re-queued with `retry_count+1`; fresh Chromium launched |
| Network partition | Watchdog marks the worker DEAD and reclaims its tasks; after the partition a new worker process heartbeats ALIVE |
| PostgreSQL restart | All processes reconnect (pool pre-ping); no process restarts needed |
| Server / Docker daemon restart | Every service comes back via `restart: unless-stopped`; state and the automation mode persist |
| Verification not completed | `VERIFICATION_TIMEOUT`; browser closed; application paused |
| Worker dies while holding a verification | `SESSION_LOST`; application `VERIFICATION_TIMEOUT` (or `UNKNOWN` if post-click) |
