SHELL := /bin/bash

.PHONY: bootstrap up down logs api-test api-lint web-check verify prod-config prod-up prod-logs
bootstrap:
	cp -n .env.example .env || true
	corepack enable
	pnpm install --no-frozen-lockfile
	cd apps/api && uv sync

up:
	docker compose up --build

down:
	docker compose down --remove-orphans

logs:
	docker compose logs -f --tail=200

api-test:
	cd apps/api && uv run pytest

api-lint:
	cd apps/api && uv run ruff check .

web-check:
	pnpm lint:web && pnpm typecheck:web && pnpm test:web && pnpm build:web

verify: api-lint api-test web-check

# Production stack (see docs/deployment/production-docker.md). Needs .env.production.
prod-config:
	docker compose --env-file .env.production -f docker-compose.prod.yml config -q && echo "compose file valid"

prod-up:
	docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build

prod-logs:
	docker compose --env-file .env.production -f docker-compose.prod.yml logs -f --tail=200
