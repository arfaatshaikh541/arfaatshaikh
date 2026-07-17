# ADR-0003: Python dependency manager, frontend package manager, mail capture tool

## Status
Accepted (Milestone 1 approval items #3, #4, #5).

## Decisions

- **`uv`** for Python dependency management and the virtual environment
  across `apps/api` and `apps/worker`, wired together as a uv workspace
  (`[tool.uv.workspace]` at the repo root) so both apps share one lockfile
  resolution and `apps/worker` depends on `apps/api`'s package directly
  rather than duplicating domain logic.
- **`pnpm` workspaces** for the frontend/JS side (`apps/web`,
  `packages/ui`, `packages/shared-types`, `packages/config`). Turborepo is
  deferred until there is a second frontend app or enough packages to
  make cross-package build orchestration worth the extra tool - right now
  a single `pnpm install` at the repo root is sufficient.
- **aiosmtpd-based capture in tests / Mailpit in Docker Compose** for
  local email capture. The application's `app.core.mail.send_email` is a
  genuine SMTP client either way; only the destination server differs
  between environments.

## Consequences
- `uv sync` must be run with `--all-packages` from the repo root (or from
  whichever member you're syncing, then again from the other) to keep
  both `apps/api` and `apps/worker`'s dependency sets installed
  simultaneously in the shared `.venv` - running `uv sync` from a single
  member's directory only installs that member's declared dependencies
  and will *remove* packages the other member needs. This is a real uv
  workspace behavior to know about, documented here after being hit
  during Milestone 1 development.
- Frontend TypeScript is pinned to **5.7.3** rather than the currently
  published `latest` (7.0.2, the new Go-based compiler) - it shipped very
  recently relative to this build and ecosystem tooling (ESLint
  type-aware rules, some editor integrations) has not caught up yet. This
  is a deliberate stability-over-bleeding-edge choice for a production
  codebase; revisit once TS7 has a few more point releases.
