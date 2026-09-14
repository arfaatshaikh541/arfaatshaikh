# World of Islam M20 - Build Fix Report

## Fixed blockers

1. **Python dependency conflict**
   - Changed `redis==6.4.0` to `redis==5.2.1` in `apps/api/pyproject.toml`.
   - This satisfies Celery 5.5.3 / Kombu Redis transport constraints.

2. **Broken pnpm workspace Docker installation**
   - Replaced the partial dependency-stage Dockerfile with a workspace-safe build that copies the complete monorepo before `pnpm install`.
   - This ensures `@world-of-islam/ui` and `@world-of-islam/shared-types` are visible during installation and build.

3. **Invalid Next.js root layout**
   - Updated `apps/web/src/app/layout.tsx` to render the required `<html>` and `<body>` elements.
   - Removed `<html>` and `<body>` from the nested locale layout.
   - Kept locale direction and language metadata on a nested wrapper.

## Verification performed in the repair environment

- Python compilation: all API and worker Python files compiled successfully.
- TypeScript syntax: 50 TS/TSX files parsed with zero syntax errors.
- Docker Compose YAML: parsed successfully; all eight services were found.
- Next.js standalone output remains enabled in `apps/web/next.config.ts`.

## Environment limitation

The repair environment does not provide a Docker daemon and cannot reach npm/PyPI registries. Therefore, an actual image build could not be completed here. The reproducible source/configuration blockers visible in the uploaded archive were repaired.

## Run

```powershell
Copy-Item .env.example .env
docker compose down -v --remove-orphans
docker builder prune -f
docker compose up --build
```

Open `http://localhost:3000` after all services become healthy.
