# World of Islam - production audit

Date: 2026-10-01. Scope: the whole repository on branch `claude/world-of-islam-webapp-9rfzue`.

**Rule used for this report:** a line says PASS only if it was actually run (the command or test is named). Anything
that could not be run here is BLOCKED or NOT_VERIFIED, with the reason. The audit environment was a Linux sandbox with
Docker, PostgreSQL 16, Chromium (Playwright) and restricted outbound access (PyPI, npm, Docker Hub and GitHub raw
reachable; quay.io, ghcr.io, the Ollama registry, Hugging Face, OpenStreetMap/Overpass and Wikipedia were not).

| Area | Result |
|---|---|
| BUILD | PASS (one component BLOCKED, see below) |
| TYPECHECK | PASS |
| LINT | PASS for the web app; FAIL for the legacy part of the API tree |
| TESTS | PASS |
| DATABASE | PASS (one NOT_VERIFIED) |
| SECURITY | PASS with documented gaps |
| AI | PASS (stub-model tests); real-model behaviour NOT_VERIFIED |
| OLLAMA | BLOCKED |
| DATA | PASS for the mechanism; most datasets are OWNER_UPLOAD_REQUIRED or LICENSE_REQUIRED |
| LICENSING | PASS (enforcement); BLOCKED on owner decisions |
| PROVENANCE | PASS (enforcement); some sources NEEDS_REVIEW |
| OFFLINE | PASS |
| PERFORMANCE | PASS (lab measurements only); load behaviour NOT_VERIFIED |
| DEPLOYMENT | PASS on one Docker host; AWS EC2 / IONOS / real TLS NOT_VERIFIED |
| BASE PATH | PASS |
| RTL | PASS (automated + screenshots); full native-speaker review NOT_VERIFIED |
| ACCESSIBILITY | PASS (axe-core, keyboard smoke test); screen-reader testing NOT_VERIFIED |

---

## BUILD - PASS (MinIO/Ollama containers BLOCKED)

- `next build` with type-checking and lint **enabled**: PASS (`ignoreBuildErrors` removed from `next.config.ts`; the real
  error it hid, a `[locale]` route type mismatch in 22 pages, was fixed with `asLocale()` in `src/i18n/route-locale.ts`).
  A production build without `NEXT_PUBLIC_WOI_API_ORIGIN`, or pointing at localhost, now fails on purpose.
- Docker images built from the repository Dockerfiles: **api, worker, web: PASS** (`uv sync --frozen`,
  `pnpm install --frozen-lockfile`; the dependence on ghcr.io was removed). In this sandbox the build needed a proxy CA
  certificate injected through a test-only overlay; the committed Dockerfiles do not contain it.
- `docker compose -f docker-compose.prod.yml config`: PASS. Full production stack (postgres, redis, migrate, api, worker, web,
  nginx, backup) started and became healthy: PASS. Only nginx publishes ports (80/443).
- **BLOCKED:** the MinIO and Ollama containers were not started because quay.io and the Ollama registry were unreachable
  from the sandbox. `/health/ready` therefore reported not-ready in the sandbox (MinIO missing); this is expected there and
  untested with MinIO present.
- Bundle size (from `next build`): 102 kB shared first-load JS; pages 102-111 kB first-load.
- Stripped of: `ignoreBuildErrors`, lint/type suppressions (`grep` finds none in `apps/web`), dev-only CSP relaxations
  (`unsafe-eval` only when `NODE_ENV!=production`), localhost fallbacks in production, placeholder secrets (the API now
  refuses to start in production with placeholder values, `tests/test_production_config.py`), and one fake UI element
  (a hard-coded "Foundations of Islam 0%" course card, replaced by a real `/learning/courses` API with an empty state).
  No demo authentication or mock API response exists in production code paths.

## TYPECHECK - PASS

- `tsc --noEmit` (web): PASS.
- `mypy` over the **whole API tree (201 files)**: PASS (8 pre-existing errors fixed, including a latent `None`
  dereference in `app/services/quran.py`).

## LINT - web PASS / API legacy FAIL

- `eslint . --max-warnings 0` (web): PASS.
- `ruff check` over the whole API tree: **FAIL, 8,987 findings** (style rules E501/S/UP in modules and tests that
  predate this work, plus ~560 unused-import/star-import findings). All new and changed API modules pass
  `ruff --select F,B`. Cleaning the legacy tree was not done.

## TESTS - PASS

| Suite | Result |
|---|---|
| API unit/contract (`pytest tests`) | 642 passed, 12 skipped (the skips are the DB integration tests below when no database is configured) |
| API integration against real PostgreSQL (`pytest tests/integration`, empty migrated DB) | 12 passed, repeatable |
| Web (`vitest`) | 36 passed (includes offline store/queue with fake-indexeddb) |
| Data validation tests (`tests/test_data_validation.py`) | included above; also fail if provenance, licence status, sources or identifiers are missing |
| Route security tests (`tests/test_route_security.py`) | included above; fail if any mutating route lacks CSRF/auth or an admin route lacks the admin check |

Coverage percentage was not measured.

## DATABASE - PASS (alembic drift NOT_VERIFIED)

- Empty PostgreSQL -> head (85 migrations): PASS, also inside the production container as a non-superuser role.
- `upgrade -> downgrade base -> upgrade`: PASS (`infrastructure/scripts/verify-migrations.sh`: 368 tables, 3,467 columns
  before and after; 1 table, `alembic_version`, after downgrade). No existing migration was edited; 0084 and 0085 were added.
  Downgrading 0084 deletes derived knowledge-graph rows that use the widened vocabulary (they are rebuilt by
  `scripts/build_knowledge_graph.py`).
- Backup/restore round trip in the production stack: PASS (nightly `pg_dump` job; `restore.sh` restores as the superuser and
  hands ownership to the application role; the app logged in afterwards).
- **NOT_VERIFIED:** `alembic check` reports pre-existing differences between the models and the migrated schema (index and
  unique-constraint naming). Not touched, as rewriting migration history was out of scope.
- Operational finding fixed during this audit: the schema forces row-level security on tenant tables, so a restore or
  `pg_dump` as the application role fails and a superuser application connection would bypass RLS. The production stack now runs
  the application as a **non-superuser role that owns the database**; the superuser is used only for backup/restore.

## SECURITY - PASS with gaps

Verified (tests or live checks):
- Authentication: session cookie `HttpOnly; Secure; SameSite=Lax; Path=/worldofislam` (observed in the production stack).
- CSRF: every mutating route requires a CSRF token except the documented pre-session and read-only POST endpoints (test).
  Logout without a token returned 403.
- CORS: allowed origin echoed with credentials; a foreign origin's preflight returned 400.
- Authorization: every `/admin` route requires the platform-administrator dependency (test; one documented exception where any
  signed-in user may only *request* a correction). Non-admin access to admin endpoints returns 403 (integration tests).
  The raw `/intelligence/generate` model endpoint, which would let a user bypass grounding, is now administrator-only.
- Rate limiting: nginx (login/register/reset: 10/min, API: 20/s) returned 429; application limiter is Redis-backed and fails
  closed in production.
- Headers/leakage: security headers on API responses, `Cache-Control: no-store` on sensitive paths, generic JSON for
  unhandled errors (no stack or connection strings), request body cap, OpenAPI/docs disabled in production (tests).
- Injection/XSS: parameterised SQL throughout; `bandit -ll` over `app/`: no issues; no `dangerouslySetInnerHTML`/`eval` in the web app.
- Secrets: none in Git (pattern scan); `.env*` ignored except the two templates; production config guard refuses placeholders.
- Dependencies: `pnpm audit` 0 known vulnerabilities (Next.js upgraded 15.5.2 -> 15.5.27 (the audit had reported 38 advisories: 3 critical, 18 high);
  dev tooling also upgraded); `pip-audit` 0 known vulnerabilities (FastAPI 0.142.2 / Starlette 1.7.0 / urllib3 2.8.0).
- SSRF: the server never fetches a user-supplied URL (directory/knowledge URLs are stored and shown as links, http(s) only).
- Uploads: dataset uploads are JSON bodies capped at 5,000 records / 12 MB; there is no binary file upload endpoint.

Gaps / NOT_VERIFIED:
- The production CSP still allows inline scripts (`script-src 'self' 'unsafe-inline'`) because of Next.js; nonce-based CSP is not done.
- No external penetration test; no automated DAST scan.
- OAuth: there is **no OAuth/OIDC implementation** in the repository (cookie-session login only), so "OAuth callback
  architecture" is NOT_IMPLEMENTED. There is also no WebSocket/SSE code, so those checks are not applicable.
- The existing "evaluate/validate" POST endpoints (milestones 8-20) are authenticated pure evaluators without CSRF; this is
  encoded in the route-security test and was not changed.

## AI - PASS (with stub models); real-model behaviour NOT_VERIFIED

Implemented and tested (`tests/test_rag.py`, `tests/integration`): classification, retrieval of verified evidence only,
ranking with a per-source cap, a transparent confidence score, **abstention** ("Insufficient verified sources."), answer
sections that keep PRIMARY SOURCE / SCHOLARLY EXPLANATION / SECONDARY SOURCE apart, scholarly-views notice (several authors on
one reference, never claiming disagreement), citation validation of any AI synthesis (rejects non-existent citations,
quotations not present in the cited source, and rulings/gradings absent from the sources), AI SYNTHESIS labelled and shown
only if validated, persistence of each run (question hash only) and an admin view of cited sources.
Tests prove: a fabricated citation is rejected, no evidence -> abstention, synthesis unavailable -> reported, not requested -> absent.
NOT_VERIFIED: behaviour with a real language model (see OLLAMA).

## OLLAMA - BLOCKED

The Ollama provider layer is contract-tested with mocked HTTP, and Ollama is the default provider with external providers
off and unsupported (`WOI_EXTERNAL_AI_ENABLED` must be false in production or the API will not start). **No model was run:**
the Ollama registry and Hugging Face are unreachable from the sandbox. On your server:
`docker compose exec ollama ollama pull llama3.1`, then ask a question with "Add an AI summary" ticked.

## DATA - PASS (mechanism)

- `data/source-manifest.json` declares 36 datasets (source, licence, provenance, version, date acquired, transformation,
  validation and publication status, importer and its version, checksum, remaining action). `docs/DATA_READINESS.md` is generated from it
  and a test fails if they diverge.
- `scripts/validate_data.py` against the policy-applied database: 9 of 9 rules PASS (Qur'an text traces to an approved
  source and matches its sha256; hadith grades have a grader and source; published rows trace to approved sources; staged
  datasets have no visible rows; knowledge records and listings have required metadata; no duplicate identifiers; every graph
  relationship has an evidence passage). Run on the un-gated development database it correctly FAILS the "hidden datasets are hidden" rule.
- Publicly visible by default: Qur'an Arabic, tajweed, Bukhari and Muslim (Arabic), Nawawi's Forty (Arabic),
  Pickthall and Yusuf Ali (1934). Everything else is staged. Counts: 7 published, 29 staged datasets.
- Importers: the new data-contract importers (`import_knowledge_records.py`, `import_directory.py`, `import_osm_mosques.py`) validate row by
  row, report failed rows, are idempotent (same file twice changes nothing), detect duplicates and can be rolled back. The older
  importers (Qur'an, hadith, tajweed, tafsir, translations) record source URL, checksum and provenance in the source
  registry, skip what already exists, and (translations, tafsir catalogue) write a failed/excluded report, but **have no rollback command**.
- Not loaded (empty state + contract + importer + admin workflow ready): fiqh, aqeedah, seerah, hadith grading, terminology, library,
  history, civilization, scholar biographies, recitation audio, and all nine directory types. Nothing was written from memory.
- Alternatives investigated: see `docs/DATA_READINESS.md` ("Legitimate alternatives investigated"). OpenStreetMap is a legitimate mosque
  source and an importer exists, but **it was not run** (Overpass unreachable here). OpenITI, Wikidata/Wikipedia, and the hadith-api grades
  were not used (licence unreadable / unreachable / grades attributed to named scholars without a licence for redistribution).

## LICENSING - PASS (enforcement) / BLOCKED (owner decisions)

Publication is enforced in code, not by convention: a dataset is visible only if it is enabled, published, has a licence status that
permits publication, and passed validation; an owner-permission publish requires who/when/basis and is audited
(`app/services/data_contracts.py::can_publish`, `publication_policy.py`; tests). The earlier "confirm before launch" sources
(English hadith translations, Hisn al-Muslim, adhkar, every tafsir edition, 482 extra translations) are staged. Open owner decisions
are listed in `docs/DATA_READINESS.md` (LICENSE_REQUIRED 8, PROVENANCE_UNCLEAR 4, NEEDS_REVIEW 3).

## PROVENANCE - PASS (enforcement)

Every stored passage keeps its source edition, checksum, licence snapshot, attribution and review state; every graph edge cites an evidence
passage; every knowledge record and listing requires source, licence and provenance (rejected otherwise); every administrative action
writes a platform audit event. NEEDS_REVIEW: the AGPL-3.0 declaration on the Bukhari/Muslim Arabic packages; the undocumented upstream of the
Nawawi data.

## OFFLINE - PASS

IndexedDB download of the Qur'an's Arabic text (114/114 surahs, no 429 through the production nginx rate limits), offline reading in a real browser
with the network disabled, offline search, an ordered write queue with newest-wins and conflict drop, a service worker that never touches `/api/`
or account pages. The Offline page lists what is AVAILABLE OFFLINE and what REQUIRES INTERNET. Not verified: iOS Safari storage eviction; background sync with no tab open.

## PERFORMANCE - PASS (lab) / load NOT_VERIFIED

Measured against the production stack on one host (localhost, no network throttling, restored database: 6,236 ayahs, 182,320 tafsir entries,
15,110 narrations, 100 k graph entities, 171 k relationships):

| Endpoint (through nginx, gzip) | p50 | p95 |
|---|---|---|
| Qur'an surah list | 23 ms | 28 ms |
| Surah reading (Al-Baqarah, 37 kB gzipped) | 36 ms | 45 ms |
| Tajweed for a surah (91 kB gzipped; 504 kB raw) | 96 ms | 304 ms |
| Unified search (Arabic or English) | ~85 ms | ~110 ms |
| Knowledge-graph entity / stats | 27 / 43 ms | 35 / 48 ms |
| Directory summary / listings | 26 / 30 ms | 33 / 35 ms |

Web vitals (Chromium, mobile viewport, lab): LCP 120-248 ms on most pages, 704-752 ms on Al-Baqarah (286 ayahs rendered at once);
CLS 0.000 on every page; INP-like interaction durations 16-24 ms. Database: every hot query uses an index (Arabic full-text GIN indexes added in
migration 0085, 0.1-18 ms); the one sequential scan is the assistant's keyword match over retrieval chunks (52 ms at 61 k chunks) and will need a text index at millions of chunks.
Fixed during measurement: Arabic search originally took 4-18 s (sequential scan of 419 MB) - now index-backed; payloads are gzipped.
Not done: virtualised ayah list for very long surahs, a sustained load test, real-network (3G/4G) throttling, Lighthouse CI.

## DEPLOYMENT - PASS on a Docker host; AWS EC2 / IONOS / real TLS NOT_VERIFIED

`docs/deployment/production-docker.md` describes both targets. Verified here: the images, the compose stack, nginx routing and TLS termination
(self-signed test certificate), health checks, restart policies, private networks (backend is `internal`), nightly backup and restore.
NOT_VERIFIED: an actual EC2 or IONOS machine, Let's Encrypt issuance and renewal hooks, the MinIO and Ollama containers (see BUILD).

## BASE PATH - PASS

Through nginx at `/worldofislam` (production build with the base path baked in): `/`, `/worldofislam`, deep links, `/en/...`, `/ar/...`,
404 pages, `robots.txt`, `manifest.webmanifest`, `sw.js` and hashed assets all correct; the `/worldofislam` redirect loop that the first
nginx config produced was found and fixed; the API is at `/worldofislam/api/v1`; cookie path, CORS, redirects, UI register/login and the
service-worker scope (`/worldofislam/`) verified in a real browser. Not applicable: OAuth callbacks, WebSocket/SSE (none exist).

## RTL - PASS (automated + screenshots)

`<html lang dir>` follows the locale; Arabic pages render right-to-left (Qur'an reader, knowledge empty states, offline page checked in screenshots);
Arabic text is marked `lang="ar" dir="rtl"`. NOT_VERIFIED: a review by Arabic readers of every string and of mixed-direction content.

## ACCESSIBILITY - PASS (automated) / manual NOT_VERIFIED

axe-core (WCAG 2.0/2.1 A and AA rules) over 20 page/locale combinations: no violations after fixing an unlabelled landmark group on the offline
page. Keyboard smoke test: focus is visible on every focusable element reached; the command palette works from the keyboard. Reduced-motion
rules are present in the stylesheet. NOT_VERIFIED: screen-reader testing, 200% zoom review, forced-colours mode.

---

## What is genuinely production-ready
Build, deployment stack, base-path routing, security baseline, source-governance pipeline, publication gating, audit trail, Arabic search, the
assistant's grounding/abstention pipeline, offline Qur'an, the directory engine, and the Qur'an/hadith/tajweed readers over the published sources.

## Not production-ready, and why
See the lists at the end of the hand-over message and `docs/DATA_READINESS.md`: data not supplied, licences not confirmed, no real LLM run,
no real server/TLS run, legacy lint, and the NOT_VERIFIED items above.
