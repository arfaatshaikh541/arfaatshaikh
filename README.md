# World of Islam

An evidence-grounded Islamic knowledge platform: Qur'an/Hadith/Tafsir with
full source provenance, a claim-grounded assistant that refuses to answer
without approved evidence, source/scholar governance, learning and research
tools, and institutional/community/federation infrastructure spanning
milestones 1 through 20, organized into twelve navigable "worlds"
(`apps/web/src/lib/worlds.ts` - Ibadah, Knowledge, Scholarship,
Civilization, Family, Life, Ummah, Charity, Journey, Intelligence,
Education, The World). See `docs/architecture/ARCHITECTURE.md` for the
milestone-to-module map, `docs/FINAL_AUDIT.md` for the base-path/security
pass, and `WORLD_OF_ISLAM_FINAL_REPORT.md` for the most recent pass (the
12-world navigation, the visual redesign, real Ibadah tools, and the
Ollama-first AI provider layer).

## Architecture

- **API**: FastAPI + SQLAlchemy (async) + Alembic, Python — 81 migrations,
  552 passing tests (`docs/architecture/ARCHITECTURE.md` has the file-count
  breakdown as of the prior pass).
- **Worker**: Celery, Python.
- **Web**: Next.js 15 / React 19, TypeScript.
- **Database**: PostgreSQL. **Cache/queue**: Redis. **Storage**: S3-compatible
  (MinIO locally).

Full rationale for keeping the backend on Python (not a Node rewrite) is in
`docs/architecture/ARCHITECTURE.md`.

## Run it — no Docker required

```bash
# API
cd apps/api
uv sync
cp ../../.env.example .env   # fill in real values
uv run alembic -c alembic.ini upgrade head
uv run uvicorn app.main:app --reload --port 8000

# Web (separate shell)
corepack enable
pnpm install
pnpm --filter @world-of-islam/web dev
```

Full instructions, including the optional Docker path, are in
`docs/deployment/local-development.md`.

Endpoints (local dev):

- Web: http://localhost:3000
- API liveness: http://localhost:8000/health/live
- API readiness: http://localhost:8000/health/ready
- API docs (non-production only): http://localhost:8000/docs

## Deploying under a subpath (`app.arfaat.com/worldofislam`)

`WOI_BASE_PATH` and `NEXT_PUBLIC_WOI_API_ORIGIN` configure the web app for a
subpath deployment; see `docs/deployment/base-path.md` for the full audit,
the required reverse-proxy configuration, and
`docs/testing/base-path-verification.md` for what was actually tested.

## Verify

```bash
cd apps/api && uv run pytest -q && uv run ruff check .
pnpm typecheck:web && pnpm lint:web && pnpm test:web && pnpm build:web
```

(`make verify` runs the equivalent from the repo root.) `ruff check .` has a
large pre-existing count of style-only findings predating this pass — see
`docs/FINAL_AUDIT.md` §10 for the breakdown; it is not a regression gate
today.

## Documentation map

- `docs/architecture/ARCHITECTURE.md` — architecture decisions and the
  milestone → module inventory.
- `docs/deployment/base-path.md` — subpath deployment, reverse proxy config.
- `docs/deployment/local-development.md` — native and Docker dev workflows.
- `docs/security/` — authentication, tenant isolation, hardening notes.
- `docs/<area>/milestone-*.md` — per-milestone architecture and acceptance
  records for milestones 7-20.
- `docs/FINAL_AUDIT.md` — base-path/Docker-optional/security pass: changed,
  tested, and left open.
- `docs/ai/provider-architecture.md` — the Ollama-first AI provider layer:
  how `AI_MODE`/`EXTERNAL_AI_ENABLED` gate it, and what was/wasn't verified.
- `WORLD_OF_ISLAM_FINAL_REPORT.md` — the 12-world navigation, visual
  redesign, and AI-provider pass: changed, tested, and left open.
