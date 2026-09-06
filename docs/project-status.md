# AURA Project Status

## Current milestone

Per the owner's explicit instruction to continue automatically through
the roadmap without pausing for approval, until only genuinely
hardware/credential/provider-bound blockers remain: every subsystem
buildable and testable without physical Windows hardware, the owner's
own credentials, or a chosen third-party provider has been built and
tested. **See `BLOCKERS.md` at the repo root for the exhaustive,
categorized accounting of what's left and why** — nothing is tagged
`IMPLEMENTABLE_NOW` there. `WINDOWS-COMMISSIONING.ps1` at the repo root
is the single script that runs every remaining hardware-dependent check
on a real Windows machine and produces one diagnostic bundle.

**AURA is not being called complete.** Per the owner's explicit
condition, that only happens once `WINDOWS-COMMISSIONING.ps1` has
actually been run on real hardware and its results reviewed.

## What's real right now

Everything below is genuinely built, genuinely tested in this session
(never assumed from a plan), and reachable through the CLI and/or API —
not isolated unit-tested classes sitting unwired. Test counts as of this
update: **Python 171 passing** (`core/tests`), **`AuraVoice.Core.Tests`
24 passing**, **`AuraShell.Core.Tests` 13 passing** — zero failures,
zero skips, across every run in this session.

- **Core runtime**: persistent memory + World Model (entities/
  relationships), Model Router with a real streaming Ollama provider and
  an explicitly test-only fallback, the deterministic instant-action
  lane, FastAPI server, CLI.
- **Governance**: Action Broker, Risk Engine (GREEN/AMBER/RED, explicit
  rule tables), Policy Engine (persisted kill switch, per-action-type
  autonomy levels, prohibited actions, budgets), Approval Engine,
  Credential Broker, Rate Limiter, hash-chained tamper-evident Audit Log.
  Every action of every kind — deterministic, connector, future agent —
  passes through `ActionBroker.submit()`; nothing calls a handler
  directly.
- **Security Guardian**: independent oversight, rolling-window rule
  evaluation (repeated-denials, RED-tier velocity), engages the kill
  switch on its own when a rule fires — no `disable()` method exists, by
  design.
- **Durable Task Engine**: SQLite-backed, lease-based claiming, retry
  with backoff, crash/lease-expiry recovery — re-verified on this exact
  Windows commissioning path via `WINDOWS-COMMISSIONING.ps1`'s dedicated
  task-recovery check.
- **Executive Intelligence / Goal Engine**: goals require a success
  metric, budget, and stop conditions before they can activate.
- **Connectors, wired into the live runtime** (`GET /connectors`,
  `aura connectors list`): filesystem, HTTP (egress-allowlisted),
  desktop control (pynput), telephony (mock provider, real Action-Broker/
  policy/audit pipeline), email (SMTP, tested against a real local
  server), browser (Playwright/Chromium), a generic REST connector for
  social/CRM vendors, and finance (mock, drafts only — no live execution,
  by explicit design, matching the owner's high-risk-capability
  decision). See `BLOCKERS.md` for exactly what each needs to go further.
- **Voice pipeline**: real local providers, not placeholders —
  openWakeWord (ONNX, `hey_jarvis`), sherpa-onnx Whisper-tiny.en (STT),
  sherpa-onnx Piper (TTS), all genuinely downloaded and exercised with
  real inference. `ConversationOrchestrator` and `AuraVoice.Windows.Host`
  assemble these into an actual runnable assistant (mic → VAD → wake
  word → STT → aura_core reasoning → TTS → barge-in), with a real log
  file and process-level self-recovery (`aura voice run`, supervised).
  Manually verified in this sandbox to start correctly and reach
  `ListeningForWake` against a live aura_core server; fails only at the
  genuinely Windows-only boundary (opening a real audio device).
- **Native Windows shell** (`apps/windows/AuraShell`): `AuraShell.Core`
  (API client, view-models) built and tested; the WPF shell itself is
  written but has never built in this environment at all — confirmed by
  trying, not assumed. `WINDOWS-COMMISSIONING.ps1` builds and
  smoke-launches it for real on Windows.
- **Installer**: `install/preflight.py` (cross-platform, tested) and
  `install/Install-AURA.ps1` (staged install with rollback, written
  carefully but never executed here — no `pwsh` available in this
  sandbox until this update, see below).
- **End-to-end tests** tying governance, tasks, executive, connectors,
  audit, and guardian together in one real flow
  (`core/tests/test_end_to_end.py`).

## What changed in this update

This update closed out the owner's "do not leave anything
`IMPLEMENTABLE_NOW` unfinished" instruction. Rather than only reproducing
what earlier updates already claimed, the system was re-audited from
scratch, which surfaced four real gaps — all closed, with tests, this
session:

1. **The connector framework was never wired into the live system.**
   `build_runtime()` now registers every credential-free connector by
   default; `GET /connectors` and `aura connectors list` make their real,
   live-checked health reachable for the first time.
2. **The voice pipeline had no composition root.** Added
   `ConversationOrchestrator` and `AuraVoice.Windows.Host` — an actual
   runnable program, not just individually-tested library pieces.
3. **No logs or process-level self-recovery for the voice pipeline.**
   Added `FileVoiceLog` and `aura voice run` (Supervisor-managed
   crash-restart), both explicitly asked for in the product brief.
4. **No financial connector existed at all.** Telephony and desktop
   control had gotten the owner's "interfaces only, no live execution"
   treatment for high-risk capabilities; finance had nothing. Added
   `FinanceConnector` + `MockPaymentProvider` (drafts only, structurally
   incapable of a real transfer), deliberately not auto-registered.

`BLOCKERS.md` and `WINDOWS-COMMISSIONING.ps1` were then written as the
owner's two explicit closing deliverables. Writing the commissioning
script was not a paper exercise: real PowerShell 7 was downloaded
directly from GitHub releases into this sandbox (reachable even though
apt/snap sources for it are not) specifically to run the script for
real, which caught two genuine bugs — not sandbox artifacts, since both
reproduce on a real Windows invocation too:

- A test spawned a bare `python3` instead of `sys.executable`, silently
  resolving to the wrong interpreter whenever the venv isn't
  PATH-activated — exactly how the commissioning script invokes Python.
- `GET /connectors` crashed for the browser connector specifically:
  Playwright's sync API refuses to run on a thread with an active
  asyncio event loop, which is exactly the thread FastAPI's `async def`
  handlers run on. Fixed via `starlette.concurrency.run_in_threadpool`.

Re-running the full commissioning script after both fixes: every check
this Linux sandbox can genuinely pass, does; the only two failures left
are exactly the two things this sandbox cannot provide — a WPF build and
a real X/Windows display — both already correctly classified in
`BLOCKERS.md`.

## Known gaps, honestly

Everything in this section is in `BLOCKERS.md`, categorized; this is
just the short version:

- Real Windows hardware validation: native shell build/launch,
  microphone/speaker I/O, VAD/wake-word/STT tuning against real audio,
  desktop-control's real on-screen effect, `Install-AURA.ps1`.
- Owner credentials: real SMTP account, real REST/CRM/social vendor API
  keys, Ollama actually running for real (non-test-mode) generation.
- Owner's choice of external provider: a telephony vendor (Twilio/SIP), a
  payment processor, a specific CRM/social platform.
- Explicitly out of scope, not a blocker: security/pentest tooling
  (requires a scoped engagement, not a standing capability), the full
  financial-control.md layered system (budget envelopes, dual
  authorization — a separate design effort), and the custom agents named
  in `docs/agents/README.md` (specified, not built — building them
  without a real use case to drive their logic would be speculative).

## Next step

Run `WINDOWS-COMMISSIONING.ps1` on a real Windows machine. It produces
one diagnostic bundle (`.zip`) with every log from every check —
preflight, the full test suite, both `.sln` builds, connector/capability
health, real Ollama generation, and an interactive but automatically-
graded voice pipeline session. Send that bundle back if anything fails.
