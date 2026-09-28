# Security review: cloud runtime, remote browser and human verification

Scope: the whole codebase as of the cloud-runtime change, with emphasis on the new attack surface
(remote browser sessions, WebSocket relay, notifications, reconciliation, container deployment).
Method: a code review (route-by-route authentication audit, template/SQL/path searches), automated
tests, and checks against the running Docker stack. Findings fixed during the review are marked **FIXED**.

| Area | Status | Evidence |
|---|---|---|
| Authentication | OK | Every route requires a server-side session except `/healthz` (DB status only), `/login`, `/static`, `/metrics` (bearer token file *or* session) and the verification WebSocket (does its own session check). scrypt password hashes; lockout after 5 failures; per-IP login throttle |
| Authorization | OK (single role) | One administrator role; all admin actions are audited. There is no multi-tenant separation: one deployment = one candidate |
| Session security | OK | Random 256-bit tokens stored as SHA-256; `HttpOnly; Secure; SameSite=Strict`; server-side expiry and logout deletion |
| CSRF | OK | Per-session token on every POST (tested); WebSocket: `Origin` must equal `Host` (CSWSH test) plus SameSite=Strict cookie |
| XSS | OK | Jinja2 autoescaping (tested with a hostile CV); CSP `script-src 'none'` on every page except `/verify/<id>`, which allows only our own static `verify.js` and a same-host WebSocket (no inline script, no `unsafe-eval`, which the test suite itself ran into) |
| SQL injection | OK | SQLAlchemy parameterised queries only; no f-string SQL in application code |
| Browser-session isolation | OK | A fresh BrowserContext per application; a held verification session exposes only that one page; session tokens are bound to a verification id, user id and a 120 s expiry |
| Raw Chromium debug interface | OK (verified) | Playwright launches Chromium over a pipe. In the running worker container the only listening sockets were the internal session server and Docker's DNS resolver, both with and without Chromium running |
| Remote session server | OK | Internal network only (`expose`, not `ports`; unreachable from the host, verified). Rejects missing, forged, expired and wrong-session tokens (tested). Input is allow-listed (click/type/key/scroll/done), bounded to the viewport, and text is capped at 256 chars. Typed text is never logged |
| WebSocket relay | OK | Session + origin + request state + expiry checks before any upstream connection; client frames over 4 KB are dropped; every session open is audited |
| Credential encryption | OK | AES-256-GCM envelope with per-record data keys, record-bound AAD and key rotation. Decryption happens in workers only (logins, SMTP, Telegram, IMAP, AI keys) |
| Secret exposure | **FIXED** | A Telegram exception message could contain the bot token (it is part of the Bot API URL) after the redactor stopped tracking it; errors are now sanitised while the secret is registered. Log redaction verified on real process logs |
| Environment separation / SSRF | OK | `production`: https to public hosts only (loopback, private, link-local and metadata addresses refused). `test`: local fixtures only. `development`: LIVE refused. Checked before navigation and again before submit |
| File upload / path traversal | **FIXED** | CV names are basenamed and leading dots stripped; the worker's temporary CV path is checked to stay inside its private temp dir (a `..` name previously resolved to the parent directory). Uploads are type-sniffed, size-capped, and stored encrypted outside any served directory |
| Rate limiting | OK | Per-host outbound limiter with backoff (in the DB); login throttle; one application dispatched at a time with daily and per-platform caps |
| Audit logging | OK | Logins, settings, mode changes, credential changes (never values), evidence views, verification page views and session opens, reconciliation decisions |
| Container privileges | OK (verified) | web/scheduler/worker run as uid 1001 with `cap_drop: ALL` (CapEff = 0), `no-new-privileges` and a read-only root filesystem with tmpfs `/tmp`. PostgreSQL keeps the defaults its entrypoint needs |
| Network exposure | OK (verified) | Published: `127.0.0.1:8000` (web), plus 80/443 when the Caddy profile is enabled. PostgreSQL and worker session ports are internal |
| Backups | OK | Dumps contain only vault ciphertext; the master key and DB password are excluded by the backup script |

## Residual risks and recommendations

* **Internal hop is plaintext.** Traffic between the web container and a worker's session server
  crosses the Docker bridge network unencrypted (frames can show personal data). This is acceptable on a
  single host; with workers on multiple hosts, use an encrypted overlay (WireGuard/Tailscale or an
  encrypted Docker overlay network).
* **Master key on disk.** `secrets/master.key` is a root-owned file readable by uid 1001. Anyone with
  root on the server can decrypt everything. Protect server access; consider full-disk encryption.
* **Human-session power.** While you hold a verification session you can type into any field of that
  page. This is by design: you are the operator. Sessions expire (configurable) and can be cancelled.
* **Single admin role.** Add accounts only for people who may control your applications.
