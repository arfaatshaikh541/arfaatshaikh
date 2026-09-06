# AURA Core — Run & Verify Locally

This is the real, working part of AURA so far: a headless core runtime with
persistent memory, a deterministic instant-action lane, and a streaming
chat interface. It was built and tested in a cloud Linux container, which
has no Windows, no audio hardware, no GPU, and no Ollama installation —
so everything below distinguishes **what has been verified here** from
**what only you can verify, on your machine.**

## The Action Broker / Policy Engine (mandatory execution gateway)

As of this update, every deterministic action goes through a real
governance pipeline before it executes — see
`docs/architecture/04-agent-architecture.md` for the design this
implements:

```
submit(ActionRequest)
  -> kill switch check (PolicyEngine)
  -> risk classification (RiskEngine: GREEN/AMBER/RED, rule-based, no model judgment)
  -> policy evaluation (PolicyEngine: autonomy level, prohibited actions, budgets)
  -> ALLOW: credential issuance (CredentialBroker) -> handler execution
  -> REQUIRE_APPROVAL: persisted to ApprovalEngine, execution deferred
  -> DENY / KILL_SWITCH_ENGAGED: rejected outright
  -> every branch writes to AuditLog (hash-chained, tamper-evident)
```

RED-tier actions (large transfers, bank-detail changes, hiring/firing,
root security changes, credential-authority grants, identity verification)
always require approval, regardless of configured autonomy level — that's
a hard rule in `PolicyEngine.evaluate`, not a default that can be
accidentally raised away. Any future connector, computer-control action,
email send, social post, phone call, finance action, deployment, or
security action registers a handler with the `ActionBroker` and is
reached *only* through `broker.submit()` — nothing is permitted to call a
handler directly.

Operate it from the CLI:

```bash
aura approvals list
aura approvals decide <approval_id> --approve --by=owner
aura kill-switch engage   # blocks every action immediately, verified in tests and by hand
aura kill-switch status
aura kill-switch disengage
aura audit show --limit 20
aura audit verify          # detects tampering; try editing audit_entries directly in the DB and re-run it
```

Or from the API: `GET /approvals`, `POST /approvals/{id}/decide`,
`POST /kill-switch/engage`, `POST /kill-switch/disengage`, `GET /audit`,
`GET /audit/verify`.

**Verified in this session**: 56 pytest tests (governance: risk engine,
policy engine, approval engine, credential broker, audit log, and a
full `ActionBroker` integration suite covering GREEN-auto-execute,
AMBER-pending-then-approved, AMBER-pending-then-denied, RED-always-
requires-approval-even-at-level-5, kill-switch-blocks-at-submit,
kill-switch-engaged-between-approval-and-resume, prohibited-actions,
missing-handler, non-LIVE-handler-results-reported-honestly, and
budget-spend-only-on-success) — **all passing**. Additionally, a real
end-to-end smoke test was run across *separate CLI process invocations*
(not just in-process test fixtures): an approval was created by one
process, listed and decided by a second, and the audit chain verified by
a third, all against the same on-disk SQLite file — proving the
persistence is real, not an artifact of shared test state.

What this governance layer does **not** do yet: it has no connectors to
gate in practice (there is nothing consequential to execute besides the
deterministic status/help/tasks/computer-control stubs), no durable
workflow engine for approvals that need to survive very long waits at
scale (today's persistence is "the row is still in SQLite," which is
real but not Temporal-grade), and no Security Guardian watching it from
outside (`docs/architecture/04-agent-architecture.md#security-guardian-
independent-oversight` — not built). Do not treat this as complete
protection; treat it as the real, tested first layer that every future
capability is now required to sit behind.

## What's genuinely proven right now (see `tests/`, 56 tests, all passing)

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

Expect `56 passed`. If you see any failure, that's a real regression —
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

### Download the voice models

Wake word, speech-to-text, and text-to-speech need real model files that
are never committed to the repo (100+ MB, binary). `aura_core.voice`
looks for them under `core/.models/` by default (override with
`AURA_VOICE_MODELS_DIR` or the individual `AURA_WAKEWORD_*`/`AURA_STT_*`/
`AURA_TTS_*` variables in `voice/config.py`). Run this once, from `core/`,
with your venv activated:

**Windows (PowerShell):**
```powershell
python -c "import openwakeword.utils as u; u.download_models(target_directory='.models/openwakeword')"

New-Item -ItemType Directory -Force -Path .models\sherpa-stt | Out-Null
Invoke-WebRequest -Uri "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-whisper-tiny.en.tar.bz2" -OutFile stt.tar.bz2
tar -xjf stt.tar.bz2 -C .models\sherpa-stt
Remove-Item stt.tar.bz2

New-Item -ItemType Directory -Force -Path .models\sherpa-tts | Out-Null
Invoke-WebRequest -Uri "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-en_US-amy-low.tar.bz2" -OutFile tts.tar.bz2
tar -xjf tts.tar.bz2 -C .models\sherpa-tts
Remove-Item tts.tar.bz2

# The TTS archive bundles its own espeak-ng-data -- point AURA_TTS_ESPEAK_DATA
# at it for this session (add it to your profile / a .env to make it permanent):
$env:AURA_TTS_ESPEAK_DATA = (Resolve-Path ".models\sherpa-tts\vits-piper-en_US-amy-low\espeak-ng-data").Path
```

**Linux/macOS:**
```bash
python -c "import openwakeword.utils as u; u.download_models(target_directory='.models/openwakeword')"

mkdir -p .models/sherpa-stt .models/sherpa-tts
curl -L -o /tmp/stt.tar.bz2 "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-whisper-tiny.en.tar.bz2"
tar -xjf /tmp/stt.tar.bz2 -C .models/sherpa-stt
curl -L -o /tmp/tts.tar.bz2 "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-en_US-amy-low.tar.bz2"
tar -xjf /tmp/tts.tar.bz2 -C .models/sherpa-tts

export AURA_TTS_ESPEAK_DATA="$(pwd)/.models/sherpa-tts/vits-piper-en_US-amy-low/espeak-ng-data"
```

Then `python install/preflight.py` (or the `voice_models`/`espeak_ng_data`
lines of `WINDOWS-COMMISSIONING.ps1`'s preflight section) should report
`PASS`, and `aura status` should show `voice.wake_word`/`voice.stt`/
`voice.tts` as `LIVE` once the API server has started at least once (the
check runs at server startup, not at import time).

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
