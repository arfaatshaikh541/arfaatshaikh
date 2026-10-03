# World of Islam

An evidence-grounded Islamic knowledge platform. Every text shows its source, licence and provenance; content appears
only when it has been verified and may lawfully be published; nothing is written from model memory. Features that need a
dataset which has not been supplied show an honest empty state ("Source not currently available for public
publication.") and activate automatically when an authorised dataset is loaded.

Start with these three documents:

- **`WORLD_OF_ISLAM_PRODUCTION_AUDIT.md`** - what was tested and the result (PASS / FAIL / BLOCKED / NOT_VERIFIED).
- **`docs/DATA_READINESS.md`** - every pending domain (records, source, licence, status, remaining action) and every data source.
- **`docs/SOURCE_VERIFICATION.md`** and **`docs/PENDING_DATA_AUDIT.md`** - which sources were examined and why each was used or not; the audit of the pending domains.
- **`docs/FEATURE_STATUS.md`** - every capability and its status.

## Architecture

```
Nginx (443/80) -> Next.js (web, basePath /worldofislam) -> FastAPI (api) -> PostgreSQL, Redis, MinIO, Ollama
                                                           Celery worker, nightly backup
```

- **API**: FastAPI + async SQLAlchemy + Alembic (86 migrations), Python 3.12.
- **Web**: Next.js 15 / React 19 / TypeScript; English and Arabic (RTL) throughout.
- **Data**: PostgreSQL (row-level security on tenant tables), Redis, S3-compatible object storage.
- **AI**: Ollama by default; no paid API; external providers are off and unsupported. See `docs/ai/provider-architecture.md`.
- **Governance**: source registry (licence, integrity, review, attribution) -> `data/source-manifest.json` -> publication
  policy -> readers, search, assistant and knowledge graph. See `docs/data-contracts.md`.

## Run it on your PC

See `docs/deployment/local-development-windows.md` (step by step, Windows) or `docs/deployment/local-development.md`.

```bash
cd apps/api && uv sync && cp ../../.env.example .env      # edit the values
uv run alembic -c alembic.ini upgrade head
uv run uvicorn app.main:app --port 8000
# second shell
corepack enable && pnpm install && pnpm --filter @world-of-islam/web dev
```

## Deploy (VPS or AWS EC2)

`docs/deployment/production-docker.md`: `docker-compose.prod.yml` (only nginx publishes ports 80/443), nginx with TLS,
health checks, restart policies, nightly backups, restore script, `.env.production.example`.
Public address: `https://app.arfaat.com/worldofislam` (`WOI_BASE_PATH=/worldofislam`, see `docs/deployment/base-path.md`).

## Verify

```bash
cd apps/api
uv run pytest -q                                                    # unit and contract tests
WOI_TEST_DATABASE_URL=postgresql+asyncpg://... uv run pytest tests/integration -q   # API against a real database
uv run python scripts/validate_data.py                              # source/licence/provenance rules on a loaded database
cd ../.. && pnpm typecheck:web && pnpm lint:web && pnpm test:web && pnpm build:web
./infrastructure/scripts/verify-migrations.sh                       # upgrade -> downgrade -> upgrade on a scratch database
```

`ruff check .` over the whole API still reports many style findings in older modules; the new and changed modules are
clean for `ruff --select F,B` and `mypy` (see the audit for the exact scope).

## Documentation map

- `docs/DATA_READINESS.md`, `docs/data-sources.md`, `docs/data-contracts.md` - data governance.
- `WORLD_OF_ISLAM_FINAL_REPORT.md` (+ `DATA_READINESS_FINAL.json`, `SOURCE_VERIFICATION_FINAL.json`, `DATA_COVERAGE_FINAL.json`) - the current honest status: **NOT_PRODUCTION_READY**, with every blocker. `data/rights-ledger*.json` records what each source says about its rights; `data/source-probes.json` what could be reached; `data/verification-prod-compose.json` how the production stack was verified (and what was not).
- `docs/FEATURE_STATUS.md` - capability status (generated from `apps/web/src/lib/worlds.ts`).
- `docs/deployment/` - production Docker, base path, local development, offline.
- `docs/architecture/ARCHITECTURE.md` - architecture decisions and the milestone -> module inventory.
- `docs/security/` - authentication, tenant isolation, hardening notes.
- `docs/archive/` - earlier reports, kept for history only.
