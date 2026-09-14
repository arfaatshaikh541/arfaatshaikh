SHELL := /bin/bash

.PHONY: bootstrap up down logs api-test api-lint web-check verify
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
