# AURA Project Status

## Current milestone
Following v0.2.0 (Action Broker / Policy Engine), per explicit owner
instruction to continue automatically without pausing for approval: a
native Windows shell (`apps/windows/`) and a real-time voice layer
(`apps/voice/`) have been scaffolded in C#/.NET, with the portions
buildable/testable in this environment actually built and tested.

## Status
Real, tested, running Python core (`/core`). Real, compiled, and
partially tested C# for the Windows shell and voice layer
(`/apps/windows`, `/apps/voice`) — see their own READMEs for the exact
verified/unverified boundary; the honest summary is: all pure logic
(view-models, API client parsing, VAD, the conversation state machine)
is built AND tested; everything touching a real window, a real
microphone, or real Windows speech synthesis is built and compiles, but
has never executed, because this environment has none of those things.

## Windows shell & voice layer (this update)

- `apps/windows/AuraShell.Core` (plain net8.0): `AuraApiClient` (real SSE
  parsing against the aura_core API's exact wire format), `ChatViewModel`,
  `StatusViewModel`, `ApprovalsViewModel`, `MainViewModel`, a hand-rolled
  `RelayCommand`/`ObservableObject` (no external MVVM package dependency).
  **13 tests, all passing** — real HTTP-shaped fakes (`FakeHttpMessageHandler`),
  not mocks of the client's own methods.
- `apps/windows/AuraShell` (net8.0-windows, WPF): `App.xaml(.cs)`,
  `MainWindow.xaml(.cs)`, a value converter. Three tabs (Chat/Status/
  Approvals) plus a kill-switch toggle, all data-bound to `MainViewModel`.
  **Cannot build in this environment** — confirmed by trying: WPF
  requires the Windows Desktop SDK, unavailable on Linux. Unverified
  beyond "carefully written, following standard WPF/MVVM patterns."
- `apps/voice/AuraVoice.Core` (plain net8.0): `EnergyVoiceActivityDetector`
  (real RMS-energy VAD), `VoiceSessionController` (the full wake/listen/
  process/speak/conversation-window/barge-in/sleep state machine), and
  the `IWakeWordDetector`/`ISpeechToText`/`ITextToSpeech` interfaces with
  honest `Null*` defaults (never fire / throw rather than fake success).
  **11 tests, all passing.**
- `apps/voice/AuraVoice.Windows` (net8.0-windows): real NAudio
  microphone-capture code (`NAudioMicrophoneSource`) and the pipeline
  wiring capture → VAD → wake-word → utterance-buffering → STT → the
  state machine → TTS (`WindowsVoicePipeline`). **Compiles successfully
  in this environment** (confirmed) — real code against NAudio's actual
  API, not a guess — but never run against a real microphone.
- `apps/voice/AuraVoice.Windows.Speech` (net8.0-windows): real Windows
  SAPI text-to-speech (`SapiTextToSpeech`, via `System.Speech`).
  **Also compiles successfully here** (somewhat surprisingly — see below)
  but never produced actual audio.
- Wake-word detection and speech-to-text are **not implemented**, only
  interfaced — they need a licensed/trained model (Porcupine) and an STT
  engine (Vosk or a cloud API) respectively, neither of which this
  session has credentials or model files for. `apps/voice/README.md`
  documents the exact next steps.

Two real bugs were caught by actually attempting builds, not by review:
the `NAudio` umbrella package pulls in a `WindowsForms` FrameworkReference
that fails to resolve on Linux (fixed by depending on `NAudio.Core` +
`NAudio.WinMM` directly, which is all the code actually uses); and a
`.csproj` XML comment containing `--` failed `dotnet sln add`'s XML
parser (fixed). Both are documented in `apps/voice/README.md` so the
reasoning isn't lost.

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

## Completed work (this update)
- `/core/src/aura_core/governance/`: the Action Broker and its supporting
  components, per `docs/architecture/04-agent-architecture.md`:
  - **Risk Engine**: deterministic GREEN/AMBER/RED classification from an
    explicit, versioned action-type/amount rule table; unknown action
    types fail safe to AMBER, never assumed safe.
  - **Policy Engine**: persisted (survives process restart) kill switch,
    per-action-type autonomy levels (0-5, unknown defaults to 0/Observe),
    prohibited-action list, and budget envelopes. RED-tier actions always
    require approval regardless of configured autonomy level — a hard
    rule in code, not a default that can be quietly raised away.
  - **Approval Engine**: persisted pending/approved/denied queue.
  - **Credential Broker** (minimal): short-lived, scoped, revocable
    tokens issued per action and revoked immediately after execution —
    the pattern every future connector's real secret exchange will use.
  - **Audit Log**: hash-chained, append-only; tamper detection verified
    by directly editing a row via raw SQL and confirming `verify_chain()`
    catches it.
  - **Action Broker**: sequences kill-switch -> risk -> policy ->
    (approval) -> credential -> handler -> audit on every call, with no
    path that skips the audit write.
- Refactored the deterministic action lane: `TriggerMap` now only resolves
  text to an `ActionRequest`; execution happens exclusively via
  `ActionBroker.submit()`. `open chrome` / `mute` are now denied at the
  policy layer (autonomy level 1, seeded because the underlying capability
  isn't connected) rather than reaching a handler at all.
- `/core/src/aura_core/runtime.py`: single `build_runtime()` used by both
  the CLI and the API, so there is one definition of how the components
  fit together.
- CLI: `aura approvals list|decide`, `aura kill-switch engage|disengage|
  status`, `aura audit show|verify`.
- API: `GET/POST /approvals`, `POST /kill-switch/engage|disengage`,
  `GET /audit`, `GET /audit/verify`.

## Completed work (v0.1.0, prior update)
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
core/src/aura_core/actions/registry.py       (rewritten this update: TriggerMap, resolution only)
core/src/aura_core/actions/builtins.py       (rewritten this update: handlers keyed by action_type)
core/src/aura_core/api/__init__.py
core/src/aura_core/api/app.py                (rewritten this update: routes through the broker)
core/src/aura_core/runtime.py                (new this update)
core/src/aura_core/governance/__init__.py    (new this update)
core/src/aura_core/governance/models.py
core/src/aura_core/governance/risk_engine.py
core/src/aura_core/governance/policy_engine.py
core/src/aura_core/governance/approval_engine.py
core/src/aura_core/governance/credential_broker.py
core/src/aura_core/governance/audit_log.py
core/src/aura_core/governance/action_broker.py
core/tests/conftest.py
core/tests/test_memory_store.py
core/tests/test_model_router.py
core/tests/test_triggers.py                  (replaces test_actions_registry.py)
core/tests/test_api_status.py
core/tests/test_api_chat_streaming.py
core/tests/test_api_governance.py            (new this update)
core/tests/test_risk_engine.py               (new this update)
core/tests/test_policy_engine.py             (new this update)
core/tests/test_approval_engine.py           (new this update)
core/tests/test_credential_broker.py         (new this update)
core/tests/test_audit_log.py                 (new this update)
core/tests/test_action_broker.py             (new this update)
```

## Tests executed (real, this session)
`python -m pytest -v` inside `/core` with a fresh virtualenv:
**56 passed, 0 failed** (final run, this update — up from 17 in the prior
update; the increase is the new governance suite: risk engine, policy
engine, approval engine, credential broker, audit log, a full
`ActionBroker` integration suite, and updated trigger/API tests). This run
found no new bugs.

Additional manual smoke tests actually executed and observed in this
session (not just unit-tested):
- v0.1.0: `aura status` and `aura chat` run for real with piped input;
  a real `uvicorn` process started and hit with `curl` for `/health`,
  `/status`, and `/chat` (SSE).
- v0.2.0 (this update): a governance flow run across **separate CLI
  process invocations** against the same on-disk SQLite file — one
  process submitted an AMBER action and got `PENDING_APPROVAL`, a second
  process listed and approved it via `aura approvals decide`, a third
  showed and verified the audit trail via `aura audit show`/`aura audit
  verify`. The approved action correctly reported `NO_HANDLER` (no social
  connector exists yet) rather than a false `EXECUTED` — the pipeline
  does not launder a missing capability into a success. The kill switch
  was engaged/disengaged via the CLI and confirmed to block/unblock
  execution both by the test suite and by hand.

An earlier v0.1.0 run had caught a real bug (SQLAlchemy Python-side UUID
defaults aren't materialized before flush, so a supersession link used a
`None` id) — fixed in `aura_core/memory/store.py`, re-run confirmed.

## Known defects
None open. (The one found during testing was fixed and re-verified in
this session — see above.)

## Security findings
The Action Broker / Policy Engine / Risk Engine / Approval Engine /
Credential Broker / Audit Log are now implemented and tested (this
update). Known, explicitly-tracked gaps in this layer, none fixed yet:
- **No Security Guardian.** Nothing outside the governance stack watches
  it independently; a bug in `PolicyEngine`/`ActionBroker` itself has no
  external backstop yet. Per `docs/architecture/04-agent-architecture.md
  #security-guardian-independent-oversight`, this is required before any
  AMBER capability goes to real Level 4 autonomy.
- **Credential Broker is minimal.** It issues opaque bookkeeping tokens,
  not real secret material, because no connector needs a real secret yet.
  It has not been exercised against an actual external credential
  exchange.
- **No rate limiting / velocity limits** on submit() yet — a misbehaving
  caller could submit unboundedly many GREEN actions. Low risk today
  (nothing GREEN has a real external effect yet) but must be added before
  any connector goes live, per `docs/security/README.md#network-security`.
- **Single-process, single-machine.** No distributed lock/lease semantics;
  fine for one owner on one machine, would need revisiting before any
  multi-device or multi-agent-process deployment.

## Deferred work
Native Windows shell and real-time voice: scaffolded this update (see
above), not finished — the shell has no packaging/installer and hasn't
been run once; voice has no wake-word or STT engine wired in at all, and
nothing has been run against real audio. Both need the owner's Windows
machine to progress further; see `apps/windows/README.md` and
`apps/voice/README.md` for exact next steps.

Still not started at all: telephony, social/email/CRM connectors,
computer-control automation, financial execution, pentesting tooling, the
multi-agent department hierarchy, and the Security Guardian. All are
designed at the architecture level in `docs/` but not implemented in
code.

## Assumptions
Unchanged from the prior entry (single owner, no external tenants,
jurisdiction/currency unconfirmed) plus: the owner has accepted that this
GitHub repo (`arfaatshaikh541/arfaatshaikh`) is public, despite it now
hosting private business-system source code.

## Next approved action
The native Windows shell and real-time voice layer instructed this
session are scaffolded (this update). Meaningful further progress on
either (running the WPF app, capturing real audio, producing real
speech, tuning the VAD, wiring a real wake-word/STT engine) requires the
owner's Windows machine and, for wake-word/STT specifically, the owner's
own API keys or model downloads — genuine blockers, not a pause for
permission. Awaiting the owner running `apps/windows/README.md` and
`apps/voice/README.md`'s steps and reporting back what actually happens
on real hardware, or further instruction on what to build next in the
meantime (e.g., a connector, or the Security Guardian).
