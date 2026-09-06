# AURA Core — Run & Verify Locally

This is the real, working part of AURA so far: a headless core runtime with
persistent memory, a deterministic instant-action lane, and a streaming
chat interface. It was built and tested in a cloud Linux container, which
has no Windows, no audio hardware, no GPU, and no Ollama installation —
so everything below distinguishes **what has been verified here** from
**what only you can verify, on your machine.**

## What's genuinely proven right now (see `tests/`, 17 tests, all passing)

- Persistent memory (episodic events, semantic facts with contradiction
  detection, decisions, commitments) — real SQLite-backed CRUD, tested.
- The deterministic instant-action lane — real, no LLM involved, tested.
- The model router's fallback/health-check logic — real, tested against an
  actually-unreachable host (proves the failure path is genuine, not
  assumed).
- The FastAPI server — actually started with uvicorn and hit with curl in
  this session (see the transcript in the PR/commit this file shipped
  with); `/health`, `/status`, `/chat` (both lanes) all respond for real.
- The CLI (`aura status`, `aura chat`) — actually run end-to-end in this
  session with piped input, not just imported and assumed to work.

## What is NOT proven yet, and why

- **Ollama integration**: `OllamaProvider` is real code (genuine streaming
  HTTP client against Ollama's `/api/chat`), but there is no Ollama install
  in this container to test it against. Its status is `READY_TO_CONNECT`,
  not `LIVE`, until you run the steps below and it passes.
- **Windows / native shell**: not attempted. This environment cannot
  compile or run a Windows application. `windows.native_shell` reports
  `NOT_CONNECTED` honestly.
- **Voice, telephony, social, email, CRM, finance, computer control,
  pentest tooling**: not implemented at all yet (by your own choice, this
  round — see the four decisions we made before I started building).
  `aura status` will show every one of these as `NOT_CONNECTED`, each with
  a one-line reason. Treat any future claim that one of these is `LIVE` as
  suspect unless it comes with the same kind of real, runnable proof this
  file gives you for the core runtime.

## Run it yourself

Prerequisites: Python 3.11+, and (optionally, for real model responses)
[Ollama](https://ollama.com) installed and a model pulled.

```bash
cd core
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[test]"
```

### Run the real test suite

```bash
python -m pytest -v
```

Expect `17 passed`. If you see any failure, that's a real regression —
report it, don't ignore it.

### Verify capability status honestly

```bash
aura status
```

Everything will show `NOT_CONNECTED` or `UNAVAILABLE` except
`actions.deterministic` and (once you run a command that touches it)
`memory.store` — that's the correct, honest state for a fresh install
with no Ollama running yet.

### Wire up a real local model

```bash
ollama serve                      # if not already running as a service
ollama pull llama3.1               # or any model you prefer
export AURA_OLLAMA_MODEL=llama3.1  # if you didn't pull llama3.1
aura status
```

`model.ollama` should now report `LIVE`. If it doesn't, `aura status`'s
detail column tells you exactly what the health check saw.

### Chat, with real streaming

```bash
aura chat
```

Type a normal question and watch tokens arrive incrementally from your
local model. Type `status`, `help`, or `show tasks` to see the
deterministic lane respond instantly with no model call.

### Run the API server

```bash
uvicorn aura_core.api:create_app --factory --host 127.0.0.1 --port 8000
curl http://127.0.0.1:8000/status
curl -N -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d '{"message":"status"}'
```

## What comes next (not started)

Per the roadmap in `docs/roadmap.md` and the mega-prompt's scope: a real
native Windows shell talking to this API, the voice pipeline, the
connector fabric (email/CRM/social) with OAuth, the Action Broker /
Policy Engine / Risk Engine / Credential Broker safety layer from
`docs/architecture/04-agent-architecture.md` (this build has none of that
gating yet — the deterministic lane and model lane are open, unguarded
functions, appropriate only because nothing here can yet take a real
consequential action), and the multi-agent department structure. Each of
these should get the same treatment this slice got: built for real, tested
for real, and reported honestly — not marked done until it is.
