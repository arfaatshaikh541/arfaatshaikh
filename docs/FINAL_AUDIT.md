# Final Audit — this pass only

Scope note up front: this pass converts the base-path/Docker/wiring/security
surface of the uploaded repository into something that can genuinely run
natively and be reverse-proxied at `/worldofislam`, and it fixes concrete
bugs found while doing that. It does **not** claim to have built new UI for
the milestones the frontend doesn't yet cover (see
`docs/architecture/ARCHITECTURE.md`, "Known gap"), does not attempt a
Node/TypeScript rewrite of the backend (see the same doc, "Decision"), and
does not stand up a live cloud deployment. Every number below is from a
command actually run in this environment during this pass, not estimated.

## 1. Files changed (25)

Diffed against the uploaded archive's extracted contents, excluding
`node_modules`, `.next`, `__pycache__`, lockfiles, and generated caches:

```
README.md
.env.example
docker-compose.yml
docs/deployment/local-development.md
apps/api/Dockerfile
apps/api/app/api/router.py
apps/api/app/api/routes/assistant.py
apps/api/app/api/routes/auth.py
apps/api/app/api/routes/retrieval.py
apps/api/app/core/config.py
apps/api/app/main.py
apps/api/app/schemas/assistant.py
apps/api/app/services/retrieval.py
apps/web/Dockerfile
apps/web/eslint.config.mjs
apps/web/next.config.ts
apps/web/src/app/layout.tsx
apps/web/src/components/auth-provider.tsx
apps/web/src/components/forgot-password-form.tsx
apps/web/src/components/islamic-assistant.tsx
apps/web/src/components/register-form.tsx
apps/web/src/components/source-registry-panel.tsx
apps/web/src/components/tafsir-reader.tsx
apps/web/src/components/token-form.tsx
apps/web/src/lib/api.ts
```

## 2. Files added (6)

```
apps/web/src/app/page.tsx
apps/web/src/app/robots.ts
docs/architecture/ARCHITECTURE.md
docs/deployment/base-path.md
docs/testing/base-path-verification.md
docs/FINAL_AUDIT.md
```

## 3. Files removed (0)

No source file, model, route, migration, service, or test was deleted.

## 4. Architecture changes

- **Decision recorded, not a rewrite**: kept FastAPI/Python backend +
  Celery worker; kept Next.js/TypeScript frontend. Rationale and the full
  milestone→module inventory are in `docs/architecture/ARCHITECTURE.md`.
- **Docker is no longer required for development.** Verified end-to-end
  natively in this environment: `uv sync` → `alembic upgrade head` against a
  real local PostgreSQL → `uvicorn` serving real HTTP traffic → `pnpm
  install` → Next.js dev/build/start, all without a Docker daemon (none was
  available in this sandbox either — confirmed by `docker info` failing to
  reach `/var/run/docker.sock`). `docker-compose.yml` and both Dockerfiles
  are kept as an optional deployment path and were fixed alongside (§6).
- **All API routes consolidated under one `/api/v1` prefix** (except
  `/health/live` and `/health/ready`, intentionally unprefixed for
  orchestrator probes). Previously only the auth router carried `/api/v1`;
  every other router (quran, hadith, tafsir, sources, ...) was mounted bare,
  which meant a path-based reverse-proxy split between the web app and the
  API was structurally impossible (see `docs/deployment/base-path.md` §4).

## 5. Security fixes (concrete, not a checklist)

1. **Rate-limit bypass via header spoofing (real, exploitable).**
   `apps/api/Dockerfile` ran uvicorn with `--forwarded-allow-ips=*`, which
   trusts an `X-Forwarded-For` header from *any* client. Combined with
   `app/core/rate_limit.py` keying limits on `request.client.host`, an
   attacker could send a different fake IP on every request and bypass the
   login/registration/password-reset rate limits entirely — a working
   brute-force vector. Fixed: the flag now reads from
   `WOI_FORWARDED_ALLOW_IPS`, defaulting to `127.0.0.1` (fails closed —
   degraded rate-limit granularity behind an unconfigured proxy, never an
   open bypass). Documented in `.env.example` and the Dockerfile comment.
2. **Session cookie not scoped to the deployment path.** Added
   `WOI_COOKIE_PATH` (`apps/api/app/core/config.py`,
   `apps/api/app/api/routes/auth.py`); production should set it to
   `/worldofislam` so the session cookie is never sent to another
   application that might later share `app.arfaat.com`.
3. **Two broken client→API wiring bugs, found while auditing every fetch
   call for the base-path work, that were silently swallowing real user-
   facing failures:**
   - `islamic-assistant.tsx` called `fetch("/backend/assistant/query")` — a
     route that existed nowhere (not in Next.js, not in the API). The
     assistant UI never worked. Fixed by implementing a real
     `POST /assistant/query` endpoint that wires the existing, tested
     classify → retrieve → safety → assemble pipeline together (previously
     only reachable as two separate calls the UI never made), and pointing
     the UI at it via `apiFetch` (credentials + CSRF included).
   - `tafsir-reader.tsx` called `fetch('/api/v1/tafsir/...')` as a raw
     relative URL — hit the Next.js server, not the API, with no
     credentials or CSRF token, so bookmarking silently failed. Fixed to
     use `apiFetch`.
4. **Checked and found already sound** (no change needed): Argon2 password
   hashing with tuned cost parameters; HMAC-hashed, constant-time-compared
   session/CSRF/verification/reset tokens (raw tokens are never persisted);
   CSRF synchronizer-token pattern (`require_csrf`); RBAC via a server-side
   `PlatformAdministrator` table lookup, never a client-supplied claim; no
   raw SQL string interpolation anywhere in `apps/api` (`grep` for
   `f"...SELECT`/`.format(...)` patterns: zero matches); no `eval`/`exec`/
   `subprocess`/`os.system` in the API; tenant/user context set via
   parameterized `set_config()` calls (`app/db/context.py`) backing
   row-level isolation; CORS uses an explicit origin allow-list (not `*`)
   as required alongside `allow_credentials=True`.
5. **`ruff` findings on hardcoded-password rules (`S105`/`S106`, 6 hits)
   checked individually**: all 6 are test fixtures using literal dummy
   passwords/secrets (`tests/test_auth_schemas.py`,
   `tests/test_config.py`, `tests/test_developer_platform_m11.py`,
   `tests/test_security.py`) — no real secret is hardcoded anywhere in the
   codebase.

## 6. Database changes

**None.** All 81 existing Alembic migrations (`20260725_0001` through
`20260726_0081`) were applied unmodified against a real local PostgreSQL 16
instance in this environment and every one succeeded — see §9. No migration
was added, edited, or reordered; no model was changed; no column, index, or
constraint was touched.

## 7. API changes

- All routers except `health` now mount under `/api/v1` (was previously
  inconsistent — see §4). This is a path change for `sources`, `quran`,
  `hadith`, `tafsir`, `retrieval`, `assistant`, `learning`, `research`,
  `community`, `scholarly`, and every milestone-8..20 router; the frontend
  was updated to match (`apps/web/src/lib/api.ts` now prepends `/api/v1`
  automatically). `auth`'s external path is unchanged
  (`/api/v1/auth/...`).
- New endpoint: `POST /api/v1/assistant/query` (see §5).
- New/changed settings on `Settings` (`app/core/config.py`):
  `cookie_path` (default `/`), `root_path` (default `""`).
- `app/services/retrieval.py` gained `search_evidence()`, extracted from the
  query body that used to live only in `app/api/routes/retrieval.py`, now
  shared by both the retrieval route and the new assistant endpoint. The
  retrieval route's response shape is unchanged.

## 8. Frontend changes

- `next.config.ts`: `basePath`/`assetPrefix` from `WOI_BASE_PATH` (empty by
  default).
- `apps/web/src/app/page.tsx` (new): fixes a real bug where the bare base
  path (the application's literal landing URL) 404'd instead of redirecting
  to the default locale — see `docs/testing/base-path-verification.md`.
- `apps/web/src/app/robots.ts` (new) + `robots` metadata in `layout.tsx`:
  the application is `noindex`ed; the public marketing page at
  `arfaat.com/worldofislam` is a separate deployment with its own SEO.
- `apps/web/src/lib/api.ts`: prepends `/api/v1` centrally; callers pass
  domain-relative paths.
- Five components updated to stop hardcoding `/api/v1` (now redundant) or,
  for two of them, to stop using a broken raw `fetch()` (§5.3).
- `apps/web/eslint.config.mjs`: excluded the auto-generated
  `next-env.d.ts` from linting (it was failing lint with a rule that
  doesn't apply to a file explicitly marked "should not be edited" by
  Next.js itself) — this took lint from 1 error/1 warning to 0 errors/1
  warning; nothing was suppressed project-wide.

## 9. Tests executed (real, in this environment)

| Suite | Command | Result |
|---|---|---|
| Alembic migration chain | `uv run alembic upgrade head` against real local PostgreSQL 16 | **81/81 migrations applied**, `20260726_0081` reached |
| Backend test suite | `uv run pytest -q` against the same real database | **544 passed**, 0 failed |
| Backend lint | `uv run ruff check .` | **7,917 pre-existing errors** (see §11 — not introduced by this pass, not fixed by this pass; confirmed by checking each file this pass touched against the same baseline style) |
| Frontend typecheck | `pnpm --filter @world-of-islam/web typecheck` | **0 errors** |
| Frontend lint | `pnpm --filter @world-of-islam/web lint` | **0 errors**, 1 pre-existing warning (after the `next-env.d.ts` fix in §8) |
| Frontend unit tests | `pnpm --filter @world-of-islam/web test` | **4/4 passed** |
| Frontend production build (default, no base path) | `pnpm --filter @world-of-islam/web build` | succeeded |
| Frontend production build (`WOI_BASE_PATH=/worldofislam`) | same, with env set | succeeded |
| Base-path runtime behavior | real standalone server (`node apps/web/server.js`), both with and without `WOI_BASE_PATH` | see `docs/testing/base-path-verification.md` for the full table — found and fixed one real bug (§8) |
| API runtime smoke test | live `uvicorn` against real Postgres+Redis: register, login, CSRF-protected logout (rejected without token, accepted with it), `/assistant/query` (correctly returns `insufficient`/`no_approved_evidence` against an empty dev DB — no fabricated answer), old bare route 404s, new `/api/v1` route 200s | all behaved as documented |
| `docker compose config` (syntax/interpolation only — **no Docker daemon available in this environment**, confirmed via `docker info`) | `docker compose config` | parses cleanly, all 8 services resolve, build args resolve |

**Tests passed: 544 (backend) + 4 (frontend) = 548.**
**Tests failed: 0.**

## 10. Tests blocked by environment

- **Docker image builds and container-to-container runs**: no Docker daemon
  in this sandbox (`docker info` reports `dial unix /var/run/docker.sock:
  connect: no such file or directory`). `docker compose config` (syntax/
  interpolation validation only) is the most that could be verified here.
  This is an environment limitation, not a code defect — the native path
  (§9) exercises the same application code the Docker images would run.
- **Live reverse proxy** (nginx or otherwise): no proxy or public DNS in
  this sandbox. `docs/deployment/base-path.md` §6 is a reference config;
  the API-side and web-side halves of the split were each verified
  directly (§9), not through an actual proxy hop.
- **TLS/HTTPS**: not exercised (loopback HTTP only).
- **Celery worker**: not started or exercised in this pass; its own code
  was not touched.
- **S3/MinIO-dependent paths**: MinIO was not started; `/health/ready`
  correctly reported `object_storage: false` and `degraded` status rather
  than silently passing — this is the health check working correctly
  against a real absent dependency, not a failure.
- **Full `ruff check .` remediation**: 7,917 pre-existing findings (mostly
  `E501`/`E702`/`E701` from a deliberately dense one-line-per-statement
  style already present throughout `apps/api`, plus `F405`/`F403` from
  star imports in some test files) were catalogued, not fixed — fixing them
  would mean touching the majority of the ~180 Python files in the backend
  for a pure style change, which is out of scope for this pass and was not
  requested.

## 11. Remaining known issues

- The frontend has no UI for most of milestones 8 and 12–20 even though the
  backend APIs exist and are tested (`docs/architecture/ARCHITECTURE.md`,
  "Known gap"). This is the largest remaining gap between "backend
  implements it" and "a user can do it in the app."
  API-route-to-page-namespace collisions for the milestones **not yet**
  wired into the frontend (e.g. if a future `/learning` *page* is added,
  it will sit at the same segment as the already-existing `/learning`
  *API* router) are avoided by the `/api/v1` consolidation in §4/§7, but
  this should stay a house rule for any new work: API routes live under
  `/api/v1`, page routes never do.
- `ruff` debt (§10) is real and pre-existing; not addressed here.
- No production secret material, TLS certificate, or DNS record exists for
  `app.arfaat.com` — none of that is something a code change can produce.

## 12. Production blockers

1. **No live deployment target exists to validate against** — everything
   in this pass was verified natively/locally; the reverse proxy, DNS, and
   TLS termination described in `docs/deployment/base-path.md` are
   reference configuration, not something exercised end-to-end.
2. **Frontend UI coverage** (§11) — most of the platform's implemented
   backend functionality is not yet reachable through the web app.
3. **Docker image builds have not been validated in this pass** — no
   daemon was available; the Dockerfiles were fixed for a real, previously-
   existing bug (`NEXT_PUBLIC_*`/`WOI_BASE_PATH` not being build args) but
   an actual `docker build` was not run here. It should be run once before
   relying on the Docker path in production.
4. **Secrets**: `.env.example` contains only placeholders; every
   `WOI_SECRET_KEY`, database password, MinIO credential, etc. must be
   replaced with real generated values before any deployment, and
   `WOI_COOKIE_SECURE=true` / a real `WOI_FORWARDED_ALLOW_IPS` value must
   be set for production (both are `false`/loopback-only by default,
   correctly fail-closed defaults, not production values).
5. **No load, penetration, or accessibility (screen-reader/WCAG) testing**
   was performed in this pass — the security review in §5 is a targeted
   code/config audit, not a penetration test, and the accessibility claims
   in the platform's existing docs (`docs/accessibility/frontend-foundation.md`)
   were not re-verified here.
