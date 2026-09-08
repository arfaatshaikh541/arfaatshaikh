# Voice-First Secure Operating Interface: what's real, what's scoped out

This document is the honest scope statement for the "voice-first secure
operating interface" redesign. It follows the same discipline every
other pass in this project has: distinguish IMPLEMENTED from STATICALLY
TESTED from UNIT TESTED from WINDOWS TESTED from HARDWARE VERIFIED, and
never claim more than what's actually true.

**The single fact that governs this entire pass**: the visual shell
(`apps/windows/AuraShell`, the WPF application) requires the Windows
Desktop SDK to even compile, and this sandbox has confirmed, every time
it's been tried this session, that it cannot -- `MSB4019:
Microsoft.NET.Sdk.WindowsDesktop.targets not found`. That means the
literal 40-point acceptance test in the request this document responds
to -- watch the backend appear on a keypress, watch it disappear, speak
to AURA and hear it reply -- cannot be executed end-to-end in this
environment at all, on any implementation. Nothing built this pass
changes that; it is a property of the sandbox, not of the code.

What *is* real, and what the rest of this document is actually about: the
security boundary Backend Mode depends on, and the state-machine logic
that decides which surface is shown, both live in code that builds and
runs on Linux -- the Python API server and the cross-platform C# core
library -- and both are fully, automatically tested here today.

## Built this pass (real, tested, wired in)

### The actual security boundary (Python, `aura_core`)

This is the part that matters most, and it is genuinely complete and
tested, independent of any UI:

- **`identity/elevation.py`'s `BackendElevationService`**: a second,
  independent authentication factor beyond ordinary device-trust
  session (`EnrollmentEngine.verify_token`). A trusted device alone is
  never enough to reach Backend Mode -- the owner's PIN (new:
  `Owner.pin_hash`/`pin_salt`/`pin_iterations`, PBKDF2-HMAC-SHA256,
  200,000 iterations, via `EnrollmentEngine.set_owner_pin`/
  `verify_owner_pin`) must be presented again. Elevation sessions live
  **only in process memory** -- never written to the database -- which
  is what makes "a crash, restart, reboot, or update never leaves
  Backend Mode elevated" true structurally, not by convention. Every
  attempt, successful or not, is written to the real hash-chained Audit
  Log (`security.backend_elevation_attempt`) without ever recording the
  PIN itself. Repeated failures trigger a real, measurable exponential
  cooldown (configurable; defaults to escalating from the 3rd
  consecutive failure). 10 tests, all real: a fresh service instance
  (simulating a restart) never inherits a session; the cooldown blocks
  even the *correct* PIN while locked out; every attempt round-trips
  through the real Audit Log.
- **`api/app.py`'s `require_backend_elevation` dependency**: independent
  of, and layered on top of, the existing `require_device_token`
  dependency. `/backend/diagnostics` and `/backend/audit` are gated by
  both. A request with a valid device token and no (or an expired)
  elevation token is rejected at **the API layer** -- not by anything a
  compromised or buggy frontend could route around. New endpoints:
  `POST /backend/pin` (set/replace the PIN -- ordinary device-session
  only, since bootstrapping a PIN can't itself require the PIN),
  `POST /backend/authenticate` (device token + PIN -> elevation token),
  `POST /backend/deauthenticate` (idempotent revoke), `GET
  /backend/session` (liveness/expiry check), `GET /interface/config`
  (ungated -- hotkey and default-mode config, no secrets). 9 tests
  through the real HTTP surface, including proving `/chat` has no path
  to elevation at all (section 21's "no backend through voice bypass"),
  and that repeated wrong PINs really do hit 429.
- **Voice as a first-class channel into the real planner/execution
  architecture, not a hardcoded command list**: `/chat` now tries
  `UniversalPlanner.plan()` (built in the prior "Universal Capability
  Layer" pass) before falling back to a conversational model response.
  A fully-resolved plan executes for real through the same Action
  Broker every other interface uses -- a step that needs approval is
  voiced naturally ("I've prepared to... Shall I proceed?") and
  execution stops there rather than cascading past the approval gate; a
  step the broker denies is reported honestly; a request the planner
  can't resolve into anything concrete still falls through to the
  ordinary model response, so normal conversation is unaffected. 4 new
  tests using a scripted model provider (the same technique
  `test_email_intent.py` and `test_universal_planner.py` already use),
  proving a real file gets written for a resolved plan, a real approval
  gate blocks execution, a mixed plan reports both halves honestly, and
  the existing conversational path is unaffected.

### The state machine and hotkey logic (C#, `AuraShell.Core` -- plain
`net8.0`, builds and tests on Linux)

- **`InterfaceModeManager`**: the section-24 state machine (Booting ->
  AuthRequired -> Authenticating -> VoiceMode -> BackendAuthRequired ->
  BackendAuthenticating -> BackendMode, plus Locked and ErrorRecovery).
  Always starts at `Booting` -- there is no constructor path, no
  persisted field, that could ever start a fresh instance in
  `BackendMode`, which is what makes "a crash while Backend Mode was
  open must never reopen it" true by construction. `RequestBackendToggle()`
  is the single hotkey entry point and resolves the asymmetry the
  product brief asks for on its own: from `VoiceMode` it requires going
  through authentication; from `BackendMode` it returns to `VoiceMode`
  immediately, no re-auth. Elevation expiring *while Backend Mode is
  open* routes back through `BackendAuthRequired`, never straight to
  `VoiceMode`, since that wasn't a deliberate exit. Invalid transitions
  throw rather than silently changing mode. 15 tests.
- **`HotkeyDefinition`/`HotkeyDebouncer`** (`HotkeyManager.cs`): a
  platform-independent hotkey representation parsed from the centralized
  config string (`Ctrl+Alt+Shift+A` by default -- see the collision
  audit below), plus real, clock-injectable debounce logic proving
  section 22's "key debounce, repeated presses, key-down/key-up races,
  duplicate OS hotkey events" requirement without needing a real
  keyboard: 20 rapid simulated presses inside the debounce window fire
  the handler exactly once. 13 tests. The actual Win32 registration
  (`RegisterHotKey`/the WM_HOTKEY message loop) needs a real window
  handle and the Windows message pump -- REQUIRES_WINDOWS_RUNTIME, not
  attempted as running code this pass (see "Not built" below).
- **`AuraApiClient`** gained `GetInterfaceConfigAsync`,
  `BackendAuthenticateAsync`, `BackendDeauthenticateAsync`,
  `GetBackendSessionAsync` -- real HTTP calls against the new endpoints
  above, tested against the existing `FakeHttpMessageHandler` harness
  (same pattern the rest of this file already used). 6 new tests.

Full C# count: `AuraShell.Core.Tests` went from 20 to 55 tests, all
passing on a clean `dotnet build`/`dotnet test` on Linux.
`AuraVoice.Core.Tests` (`VoiceSessionController`, `ConversationOrchestrator`,
`VoiceCommandPhrases`) is unchanged this pass -- it already implemented
"stop listening"/"close your ears" (real state transition, not a visual
mute) and barge-in (`OnBargeIn()`, stops the current response and
resumes listening) correctly and completely in an earlier pass; nothing
here needed to duplicate it.

## Not built this pass, and why

- **The actual WPF Voice Mode / Backend Mode screens** (the orb,
  waveform, cinematic visual identity section 1 and 29 describe). This
  is real, substantial XAML/animation work that this sandbox cannot
  compile, render, or visually verify at all -- writing it blind, with
  no way to confirm it even builds, risks producing exactly the
  "screens were created" false-completion signal section 35 explicitly
  warns against. `InterfaceModeManager` and `AuraApiClient`'s new
  methods are the real, tested contract those screens need to bind to;
  the screens themselves are `REQUIRES_WINDOWS_RUNTIME` for both
  building and any visual verification.
- **`Win32HotkeyManager`** (the concrete `IHotkeyManager` using
  `RegisterHotKey`/`UnregisterHotKey` and a `HwndSource` message hook).
  Needs a real Win32 window handle and message loop to mean anything;
  `REQUIRES_WINDOWS_RUNTIME` for both compiling in its natural home (the
  WPF project) and for any real verification that it registers a real
  system-wide hotkey.
- **Windows Hello / biometric authentication.** `BackendElevationService`
  is built around a PIN today because that's the one factor this sandbox
  can actually implement and verify end-to-end without Windows APIs or
  hardware. The service's `authenticate(device_token, pin)` contract is
  intentionally narrow enough that a Windows Hello factor could be added
  as an alternative credential path later without changing the session/
  elevation model itself -- but that addition is not attempted here.
- **Real microphone capture, device enumeration, echo cancellation,
  noise suppression, Bluetooth/default-device-change handling.** All of
  section 17's audio-pipeline requirements need real Windows audio APis
  (NAudio) and real hardware; this sandbox has neither. `docs/
  FINAL_COMPLETION_AUDIT.md`'s existing voice rows already carry this
  status from earlier passes; nothing here changes it.
- **The literal 40-step final acceptance test** (section 39 of the
  request). Steps 1-6 and 11-19 specifically require a running WPF
  process, a real hotkey registered with real Windows, and real
  audio hardware -- none of which can exist in this sandbox. What can be
  and was verified: every *server-side* precondition those steps depend
  on (the elevation boundary, the audit trail, the state machine's
  transition rules, the voice-to-execution wiring) really works, proven
  by real automated tests, not by narration.
- **Regating every existing device-token-gated endpoint behind backend
  elevation.** Only the two new endpoints that expose data beyond
  ordinary operational state (`/backend/diagnostics`, `/backend/audit`)
  require elevation. Endpoints Voice Mode itself legitimately needs
  during normal operation (mandate reports, task status, `/chat` itself)
  were deliberately left on the existing device-trust boundary --
  re-gating them would have broken legitimate voice-session
  functionality (e.g. "what's happening with Gridkeep?") for no real
  security benefit, since that data was never backend-exclusive to begin
  with.

## Hotkey collision audit

Chosen default: **`Ctrl+Alt+Shift+A`**, centralized in
`aura_core.config.Settings.backend_toggle_hotkey` (env override:
`AURA_BACKEND_TOGGLE_HOTKEY`) and served to the shell via the ungated
`GET /interface/config` endpoint -- never hardcoded in UI code.

Audited against, from training-data knowledge of each surface's
documented default bindings (not verified against a live instance of
each product in this sandbox -- flagged honestly):

| Surface | Relevant defaults | Collision? |
|---|---|---|
| Windows shell | `Win+*` (task switching, snap, settings flyouts), `Alt+Tab`, `Ctrl+Alt+Del`/`Ctrl+Shift+Esc`, `Ctrl+Alt+Arrow` (some GPU driver rotate shortcuts) | No -- none use the 3-modifier `Ctrl+Alt+Shift` combination without also involving `Win` |
| Browsers (Chrome/Firefox/Edge) | `Ctrl+Shift+<letter>` for various panels (e.g. `Ctrl+Shift+J` DevTools console, `Ctrl+Shift+N` incognito); none documented at `Ctrl+Alt+Shift+<letter>` | No |
| IDEs (VS Code, Visual Studio, JetBrains) | Heavy use of `Ctrl+K <key>` chords and `Ctrl+Shift+<letter>`; `Ctrl+Alt+<letter>` used sparingly (e.g. VS Code's `Ctrl+Alt+Windows` not applicable to `A`); no common default at `Ctrl+Alt+Shift+A` specifically | No known collision, though a specific IDE extension could theoretically rebind it -- flagged as a residual risk, not eliminated |
| Accessibility (Narrator, Magnifier, high contrast) | Narrator: `Ctrl+Win+Enter`; Magnifier: `Win+=`/`Win+-`; High contrast toggle: `Left Alt+Left Shift+PrtScn`; sticky/toggle/filter keys: repeated modifier presses, not a fixed combo | No -- high contrast's combo uses PrtScn, not `A`, and is left-modifier-specific, not the same chord |
| AURA's own existing registrations | No pre-existing global hotkey exists in this codebase before this pass (grepped: no prior `RegisterHotKey`/hotkey config) | No collision, nothing to conflict with |

**What this audit is, and isn't**: a documented reasoning pass against
each surface's commonly-published default bindings, exactly what section
8 asks for before finalizing a candidate. It is not a live collision
test against a running Windows machine with every listed application
installed -- that requires the Windows hardware this sandbox doesn't
have, and would be `REQUIRES_PHYSICAL_WINDOWS_VALIDATION`. The
configuration is centralized specifically so a real collision found
during actual Windows commissioning is a one-line config change
(`AURA_BACKEND_TOGGLE_HOTKEY`), not a code change.

## Summary

The real security boundary Backend Mode depends on -- the part where a
bug or bypass would actually matter -- is built, and is enforced at the
API layer independent of any UI, exactly as the request demanded
("Do not rely on CSS visibility for security"). The state machine that
decides which screen is shown is built and exhaustively tested. What
remains is real, substantial, and named honestly: the actual Windows
visual shell, the actual OS-level hotkey registration, and everything
that needs real audio hardware or a real Windows session to verify.
