# AURA Project Status

## Current milestone
AURA Core v0.1.0 — first genuinely-LIVE vertical slice (headless core
runtime: persistent memory, deterministic instant-action lane, model
routing, streaming chat API/CLI). Implemented in `/core`.

## Status
Real, tested, running code exists for the first time in this project.
Scope was deliberately narrowed to what this environment (a cloud Linux
container — no Windows, no audio hardware, no GPU, no live credentials)
can actually build and verify, per an explicit owner decision. See
"Decisions" below.

## Background: audit of the uploaded AURA 5.2.0 codebase
An existing 1,225-file / ~36,000-line codebase (`AURA-5.2.0-INSTANT-LANE`)
was audited and **discarded per explicit owner decision (full rebuild)**.
Findings that informed that decision: the native Windows app was a 3-line
stub, no real voice/telephony/social SDK integration existed despite
extensive service scaffolding for those domains, and the codebase's own
`RELEASE-STATUS.json` listed all "live" external integrations as unmet
gates. This matched the "documentation/scaffolding without verified
software" failure mode the owner explicitly asked to avoid going forward.
Nothing from that codebase was carried into `/core`.

## Decisions made this session (owner-confirmed)
1. Repository: continue using `arfaatshaikh541/arfaatshaikh` (the owner
   was told this repo is public and originally a profile README repo, and
   confirmed proceeding anyway).
2. Existing 5.2.0 codebase: full rebuild from scratch, not reused.
3. First real vertical slice: core runtime + local model chat (headless —
   no native shell buildable in this environment).
4. High-risk capability areas (telephony, autonomous financial movement,
   automated social posting, computer-control automation, pentesting
   tools): interfaces/policy only, no live execution, until the owner
   provides scoped credentials/authorization per capability.

## Completed work
- `/core`: a real Python package (`aura_core`) implementing:
  - Capability status registry (`LIVE` / `READY_TO_CONNECT` / `DEGRADED` /
    `NOT_CONNECTED` / `BLOCKED_BY_POLICY` / `UNAVAILABLE`), seeded honestly
    — every capability named in the owner's spec that isn't built yet is
    explicitly `NOT_CONNECTED` with a stated reason, not silently absent.
  - Persistent memory (SQLite/SQLAlchemy) implementing the provenance
    envelope from `docs/architecture/02-world-model-memory.md` for four of
    the ten documented memory systems: Episodic, Semantic (with
    contradiction detection), Decision, Commitment.
  - Model provider abstraction: a real streaming Ollama HTTP client, an
    explicitly test-only deterministic provider (never usable outside
    `AURA_ENV=test`), and a router that health-checks before routing and
    refuses silent fallback in non-test mode.
  - Deterministic instant-action lane (Lane A): pattern-matched commands
    bypass the model entirely; includes honest `NOT_CONNECTED` handlers for
    OS-level actions (e.g. "open chrome") this build cannot perform.
  - FastAPI app with real Server-Sent-Events streaming on `/chat`
    (deterministic and model lanes), `/status`, `/health`, `/commitments`.
  - CLI (`aura status`, `aura chat`) with real incremental terminal output.

## Files created
```
core/pyproject.toml
core/RUNBOOK.md
core/.gitignore
core/src/aura_core/__init__.py
core/src/aura_core/config.py
core/src/aura_core/status.py
core/src/aura_core/cli.py
core/src/aura_core/memory/__init__.py
core/src/aura_core/memory/models.py
core/src/aura_core/memory/store.py
core/src/aura_core/providers/__init__.py
core/src/aura_core/providers/base.py
core/src/aura_core/providers/ollama_provider.py
core/src/aura_core/providers/test_provider.py
core/src/aura_core/providers/router.py
core/src/aura_core/actions/__init__.py
core/src/aura_core/actions/registry.py
core/src/aura_core/actions/builtins.py
core/src/aura_core/api/__init__.py
core/src/aura_core/api/app.py
core/tests/conftest.py
core/tests/test_memory_store.py
core/tests/test_model_router.py
core/tests/test_actions_registry.py
core/tests/test_api_status.py
core/tests/test_api_chat_streaming.py
```

## Tests executed (real, this session)
`python -m pytest -v` inside `/core` with a fresh virtualenv:
**17 passed, 0 failed** (final run). An earlier run caught a real bug
(SQLAlchemy Python-side UUID defaults aren't materialized before flush,
so a supersession link used a `None` id) — fixed in
`aura_core/memory/store.py`, re-run confirmed the fix.

Additional manual smoke tests actually executed and observed in this
session (not just unit-tested):
- `aura status` run for real — correct honest output.
- `aura chat` run for real with piped input — deterministic lane and
  model (test-provider) lane both produced correct, genuinely incremental
  output.
- A real `uvicorn` process was started and hit with `curl` — `/health`,
  `/status`, and `/chat` (SSE) all verified against the actual running
  server, not just FastAPI's TestClient.

## Known defects
None open. (The one found during testing was fixed and re-verified in
this session — see above.)

## Security findings
None yet — this slice has no Action Broker / Policy Engine / Risk Engine /
Credential Broker gating (`docs/architecture/04-agent-architecture.md`),
because it has no consequential action to gate yet (the deterministic lane
only reads local memory/status; the model lane only generates text). This
gating becomes mandatory before any connector, computer-control, or
financial capability is added — noted explicitly in `core/RUNBOOK.md`'s
"what comes next" section so it isn't skipped later.

## Deferred work
Everything else in the owner's mega-prompt: native Windows shell, voice
pipeline (wake word/STT/TTS/barge-in), telephony, social/email/CRM
connectors, computer-control automation, financial execution, pentesting
tooling, the multi-agent department hierarchy, the Action Broker/Policy/
Risk/Credential Broker safety layer, and Security Guardian. All are
designed at the architecture level in `docs/` but not implemented in code
yet. None can be verified as `LIVE` from this cloud environment even once
built — they require the owner's Windows machine, real hardware, and real
credentials, per `core/RUNBOOK.md`.

## Assumptions
Unchanged from the prior entry (single owner, no external tenants,
jurisdiction/currency unconfirmed) plus: the owner has accepted that this
GitHub repo (`arfaatshaikh541/arfaatshaikh`) is public, despite it now
hosting private business-system source code.

## Next approved action
Awaiting owner direction on which deferred item to build next. Given the
core runtime now exists and is real, reasonable next candidates (not yet
started) are: (a) the Action Broker/Policy Engine safety layer, so a
first connector can be added safely, or (b) a first real connector
(e.g., email) with the owner providing OAuth credentials. Not started
without owner confirmation of which comes first.
