# Architecture

## Decision: keep the Python/FastAPI backend, drop Docker as a requirement

The uploaded repository is a pnpm monorepo:

```
apps/api     FastAPI + SQLAlchemy (async) + Alembic + Celery integration   — Python
apps/worker  Celery worker                                                — Python
apps/web     Next.js 15 / React 19 / TypeScript                           — Node
packages/*   Shared TS types, UI components, contract packages            — Node
```

`apps/api` is not a thin scaffold. As of this pass:

- **123** Python source files across `app/models`, `app/services`, `app/api/routes`
  (~9,500 lines in models+services alone).
- **81** Alembic migrations (`20260725_0001` → `20260726_0081`), one continuous,
  linear history — no branches, no down-revision gaps.
- **61** test modules under `apps/api/tests`, largely one per milestone/subsystem
  (`test_civilization_os_m18.py`, `test_developer_platform_m11.py`, etc.).
- **30** mounted API route modules covering everything from Qur'an/Hadith/Tafsir
  reading and source governance to institutional federation and platform-v1
  release acceptance (full list and milestone mapping below).
- Real security primitives already in place: Argon2 password hashing with
  tuned cost parameters, HMAC-based token hashing, constant-time comparison,
  a settings validator that rejects a `SECRET_KEY` under 32 characters,
  parameterized SQLAlchemy queries throughout (no raw string interpolation
  into SQL), and per-route RBAC dependencies (`require_platform_administrator`,
  `require_csrf`, tenant-scoped queries).

Rewriting this to Node/TypeScript, as the brief's "preferred direction"
suggested if a genuine Node-only architecture were achievable, would mean
re-deriving 81 migrations' worth of schema decisions, re-implementing the
grounded-answer/claim-validation pipeline, re-implementing tenant isolation,
and re-testing all of it — with no functional benefit, and a severe risk of
silently dropping or subtly changing governance rules that took 20 milestones
to encode. That is exactly the "superficial rewrite that destroys existing
functionality" the brief says not to do. **Decision: the backend stays
Python/FastAPI.** The frontend was already Node/Next.js and needed no
migration.

What *did* need to change, and what this pass changed, is Docker being load-
bearing for ordinary development. It wasn't structurally required — Postgres,
Redis, and the two Python/Node processes are all things that run fine
natively — it was only *documented* as a Docker-first workflow
(`docker compose up --build`, per the old `FIX_REPORT.md`). See
`docs/deployment/local-development.md` for the native (`uv` + `pnpm`) path
this pass verified actually works end-to-end without a Docker daemon, and
`docker-compose.yml`/the two Dockerfiles remain as an optional deployment
path (now also fixed to bake `NEXT_PUBLIC_*`/`WOI_BASE_PATH` in at build time
— see `docs/deployment/base-path.md` §5).

## Runtime shape

```
Browser ──HTTPS──> reverse proxy ──> apps/web  (Next.js, port 3000)
                                 └─> apps/api  (FastAPI, port 8000) ──> PostgreSQL
                                                                    └─> Redis (sessions/rate-limit/Celery)
                                                                    └─> S3-compatible storage (MinIO locally)
                        apps/worker (Celery) ─────────────────────────┘
```

The web app calls the API directly from the browser (`credentials: "include"`,
session cookie + CSRF header — `apps/web/src/lib/api.ts`), not through Next.js
API routes/rewrites. In production both are reverse-proxied under the same
`app.arfaat.com` origin so this is a same-origin call; see
`docs/deployment/base-path.md`.

## Milestone → module inventory

This maps the milestones the brief asks to preserve to the actual backend
modules implementing them, so nothing here is asserted without a file to
point at. Alembic ranges are inclusive; route modules are under
`apps/api/app/api/routes/`, all mounted under `/api/v1` (see
`docs/deployment/base-path.md` §4).

| Milestone (per brief) | Migrations | Route module(s) | Models / services |
|---|---|---|---|
| 1-6: platform foundation, identity, tenancy, security hardening, source registry/lifecycle/claim provenance, Qur'an+Hadith+Tafsir foundation & import & reading, translation governance, recitation accessibility, retrieval foundation, grounded-answer pipeline, assistant safety | `0001`-`0025` | `auth`, `organisations`, `sources`, `quran`, `hadith`, `tafsir`, `retrieval`, `assistant` | `identity.py`, `tenancy.py`, `sources.py`, `quran.py`, `hadith.py`, `tafsir.py`, `retrieval.py`, `assistant.py`, `assistant_safety.py`, `source_lifecycle.py`, `source_provenance.py` |
| 7: Learning platform | `0026`-`0029` | `learning` | `learning.py` (model + service) |
| 8: Research workspace, community moderation, scholarly collaboration, knowledge network | `0020`, `0030`-`0033` | `research`, `community`, `scholarly`, `knowledge_network` | `research.py`, `community.py`, `scholarly.py`, `knowledge_graph.py`, `knowledge_network.py` |
| 9: AI orchestration, multilingual AI, personalization, AI quality hardening | `0034`-`0037` | `ai_orchestration`, `multilingual_ai`, `personalization_ai`, `ai_quality` | matching `app/services/*` |
| 10: Deployment hardening, operations resilience, compliance/enterprise readiness, launch governance | `0038`-`0041` | `deployment`, `operations`, `compliance`, `launch_governance` | matching `app/services/*` |
| 11: Developer platform (access, ecosystem, partner governance) | `0042`-`0045` | `developer_platform` | `developer_access.py`, `developer_ecosystem.py`, `developer_partners.py`, `developer_platform.py` |
| 12: Distributed knowledge sync (transport, integrity, governance acceptance) | `0046`-`0049` | `knowledge_network` (sync surfaces) | `knowledge_sync*.py` (4 modules) |
| 13: Institutional network, regionalization/residency, public trust & transparency, global rollout | `0050`-`0053` | `institutional_network` | `institutional_network.py` |
| 14: Civilizational infrastructure — preservation archives, semantic search, offline distribution, resilience | `0054`-`0057` | `civilizational_infrastructure` | `civilizational_infrastructure.py` |
| 15: Living civilization — scholarly provenance, research/education, community analytics, platform maturity | `0058`-`0061` | `living_civilization` | `living_civilization.py` |
| 16: Ummah services — zakat/waqf, humanitarian safeguarding, mosque/community services, crisis acceptance | `0062`-`0065` | `ummah_services` | `ummah_services.py` |
| 17: Global ummah network — federation identity, interoperability search, privacy & scholarship, resilience | `0066`-`0069` | `global_ummah_network` | `global_ummah_network.py` |
| 18: Civilization OS — scholarly lineage, translation governance, verifiable credentials, events, policy/operations, continuity/succession | `0070`-`0073` | `civilization_os` | `civilization_os.py` |
| 19: Islamic life — prayer-time/timekeeping, Hijri calendar, halal & ethical commerce, Islamic finance governance, family safeguarding, heritage stewardship | `0074`-`0077` | `islamic_life` | `islamic_life.py` |
| 20: Platform v1.0 — integration, security & release governance, operations performance, v1.0 acceptance | `0078`-`0081` | `platform_v1` | `platform_v1.py` |

Per-milestone architecture notes, completion reports, and portable-acceptance
evidence already exist under `docs/<area>/milestone-*.md` for milestones
7-20 and were not rewritten by this pass — they are the authoritative record
of what was implemented and how it was verified at the time. This pass adds
`docs/FINAL_AUDIT.md` for what changed *in this pass specifically*.

## Known gap this pass closed: the frontend only surfaces a subset

`apps/web` has real pages for auth, dashboard, organisations, source
registry, the Qur'an/Hadith/Tafsir readers, learning, and the evidence-
grounded assistant. It does **not** have UI for most of milestones 8, and
12-20 (research workspace, community, institutional network, civilizational
infrastructure, living civilization, ummah services, global network,
civilization OS, islamic life, platform-v1) even though the backend APIs for
them exist and are tested. Building real, non-mock UI for all of those is a
multi-week frontend effort on its own and was out of scope for this pass;
see `docs/FINAL_AUDIT.md` for exactly what was and wasn't done, so this gap
is recorded rather than papered over with placeholder pages (which the brief
explicitly prohibits).

## Two real bugs found and fixed while auditing base-path/API wiring

While auditing every place the frontend calls the API (required for the
base-path work — a wrong path is exactly how "accidental request to `/api/…`
instead of `/worldofislam/api/…`" happens), two pre-existing, unrelated to
base-path features were found silently broken and fixed:

1. `islamic-assistant.tsx` called `fetch("/backend/assistant/query")` — a
   relative URL with no such Next.js route and no such API route either (the
   API only exposed `/assistant/classify` and `/assistant/assemble`
   separately). The assistant UI was non-functional. Fixed by adding a real
   `POST /assistant/query` endpoint (`apps/api/app/api/routes/assistant.py`)
   that composes the existing, tested `classify_question` →
   `search_evidence` → `evaluate_safety` → `assemble_grounded_answer`
   pipeline, and pointing the UI at it through `apiFetch`.
2. `tafsir-reader.tsx` called `fetch('/api/v1/tafsir/...')` as a relative
   URL (hits the Next.js server, not the API, and without credentials or a
   CSRF token) instead of `apiFetch`. Fixed to use `apiFetch`.

Both are documented in `docs/FINAL_AUDIT.md` under "Security/correctness
fixes" with the exact before/after.
