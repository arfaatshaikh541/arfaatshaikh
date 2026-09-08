# Voice-First Secure Operating Interface: what's real, what's still unverified

This document is the honest scope statement for the "voice-first secure
operating interface" redesign, updated after the pass that actually wrote
the WPF shell itself (bootstrap, Voice Mode / Backend Mode / authentication
screens, the real Win32 hotkey manager, and the Windows session monitor).
It follows the same discipline every other pass in this project has:
distinguish IMPLEMENTED from UNIT TESTED from STATICALLY REVIEWED from
WINDOWS TESTED from HARDWARE VERIFIED, and never claim more than what's
actually true.

**The single fact that still governs this entire area**: `apps/windows/AuraShell`
(the WPF application) targets `net8.0-windows` with `UseWPF=true`, which
requires the Windows Desktop SDK to even compile, and this sandbox has
confirmed, every time it's been tried across every pass this session, that
it cannot — `MSB4019: Microsoft.NET.Sdk.WindowsDesktop.targets not found`.
That has not changed and cannot change without a real Windows build
environment. What *has* changed this pass: the WPF project's source files
themselves — the ones that were previously left unwritten specifically
because they couldn't be compile-checked — now exist, are written against
the already-tested `AuraShell.Core` contracts, are believed correct after
careful manual review (XAML well-formedness checked with an XML parser;
every `.cs` file's braces balanced; every type/namespace/method reference
cross-checked by hand against the real APIs it calls), but have **never
been compiled, run, or visually verified**, because nothing in this sandbox
can do that. Anyone reading this should treat the WPF-only files below as
"written carefully, not proven" until a real Windows build confirms it.

## What actually changed this pass

Previously this document said the WPF screens, `Win32HotkeyManager`, and
Windows session-lock handling were "not built, and why." That is no longer
accurate — they are now written. What's true now:

- **`App.xaml.cs`** no longer shows `MainWindow` as a pre-built
  Chat/Status/Approvals dashboard. It builds the same `AuraApiClient` as
  before, constructs one `InterfaceShellViewModel` (new — see below), and
  shows exactly one window whose content is driven entirely by that view
  model's mode. There is no code path in this file, or anywhere else in
  the project, that can display Backend Mode content before a real
  authenticated transition reaches `BackendMode`.
- **`MainWindow`** is no longer the dashboard itself — it is now the
  mode-driven shell: a single `ContentControl` whose content is swapped
  between four views as `InterfaceModeManager.ModeChanged` fires:
  `AuthenticationView` (Booting / AuthRequired / Authenticating / Locked /
  ErrorRecovery), `VoiceModeView` (VoiceMode), `BackendChallengeView`
  (BackendAuthRequired / BackendAuthenticating), and `BackendModeView`
  (BackendMode). It also owns the `Win32HotkeyManager` and
  `SystemSessionMonitor` instances (created once a real `HWND` exists, via
  `SourceInitialized`) and disposes both on close.
- **`Views/VoiceModeView.xaml`** is the actual minimal voice screen: one
  central orb (an `Ellipse` with a `DropShadowEffect` glow) whose color and
  label are driven by `VoiceModeViewModel.State` — which is itself driven
  by consuming aura_core's real `/voice/state/stream` Server-Sent-Events
  push (see below), never a timer and never a hardcoded animation. No
  sidebar, no transcript, no tables. A mute toggle calls
  `VoiceModeViewModel.SetMuted`, which is explicitly documented as
  UI-visible-only (see "Not built" below — it does not reach any real
  audio pipeline, because no real audio pipeline capture-gating exists in
  this codebase yet).
- **`Views/BackendChallengeView.xaml`** is the real second-factor PIN
  screen the hotkey opens: a `PasswordBox` (never a plain `TextBox` — the
  PIN is never bound as visible text), wired via `PasswordChanged` into
  `InterfaceShellViewModel.BackendPinInput`, with Submit/Cancel calling
  the already-tested `SubmitBackendPinCommand`/`CancelBackendAuthCommand`.
  A failed attempt shows one generic message ("Backend authentication
  failed.") — this view has no way to know, and does not try to guess,
  whether the PIN or the device was wrong.
- **`Views/BackendModeView.xaml`** is where the previous MainWindow
  dashboard's Chat/Status/Approvals tabs and the kill switch now live —
  migrated, not deleted, exactly matching the requirement that Backend
  Mode is where that functionality resurfaces, never the default startup
  screen. It gained two new tabs, **Diagnostics** and **Audit Trail**,
  bound to `InterfaceShellViewModel.Diagnostics`/`AuditEntries`, which are
  populated from the real `/backend/diagnostics` and `/backend/audit`
  endpoints the moment Backend Mode is entered, and explicitly cleared
  (not just hidden) the moment Backend Mode is left, by the same
  `LeaveBackendModeAsync` codepath that revokes the elevation token.
- **`Views/AuthenticationView.xaml`** is the actual production startup
  screen: a single centered status line plus, only when there's something
  to act on, one button (Retry when device verification failed, Recover
  when `ErrorRecovery` was entered). No credential form exists here
  because there is no interactive owner credential this build asks for at
  startup — see "the real substitute for Windows Hello" below.
- **`Win32HotkeyManager`** (`apps/windows/AuraShell/Win32HotkeyManager.cs`)
  is now a real, complete implementation of `AuraShell.Core.IHotkeyManager`
  using `RegisterHotKey`/`UnregisterHotKey` (`user32.dll`) and a
  `HwndSource.AddHook` message filter for `WM_HOTKEY`, built on top of the
  already-tested `HotkeyDebouncer`/`HotkeyDefinition`. It fails closed and
  reports why (`AlreadyInUse` via `Marshal.GetLastWin32Error() ==
  ERROR_HOTKEY_ALREADY_REGISTERED`, `Unsupported` for an unparseable key
  name, `Failed` for anything else) rather than silently doing nothing. A
  re-entrancy gate (`ReleaseProcessingGate`, released once
  `InterfaceShellViewModel.RequestBackendToggleAsync` finishes) prevents a
  second WM_HOTKEY arriving mid-transition from starting a concurrent
  toggle. **Never compiled or exercised against a real Win32 window** —
  the debounce/parsing logic it's built on is the part that's actually
  unit tested (`HotkeyManagerTests.cs`, on Linux).
- **`SystemSessionMonitor`** (`apps/windows/AuraShell/SystemSessionMonitor.cs`)
  is a real implementation of section 16's lock/unlock/logoff/sleep/resume
  handling: `WTSRegisterSessionNotification` plus a `WM_WTSSESSION_CHANGE`
  hook for lock/unlock/logoff/console-disconnect, and a `WM_POWERBROADCAST`
  hook for suspend/resume — both mapped to the same `Locked`/`Unlocked`
  events, wired in `MainWindow.xaml.cs` directly to
  `InterfaceShellViewModel.OnSystemLockedAsync`/`OnSystemUnlockedAsync`.
  Sleep is deliberately treated identically to a lock: elevation must not
  survive a suspend/resume cycle any more than a lock/unlock cycle.
  **Never exercised against a real Windows session** — no lock, sleep, or
  logoff event has actually been observed triggering this code.
- **`InterfaceShellViewModel`** (new, in `AuraShell.Core` — plain
  `net8.0`, builds and tests on Linux) is the composition root that makes
  all of the above real rather than aspirational: it owns
  `InterfaceModeManager`, `VoiceModeViewModel`, and the existing
  `MainViewModel` (Backend Mode's Chat/Status/Approvals), and performs
  every network side effect a mode transition requires that
  `InterfaceModeManager` itself deliberately never does (it has no network
  access at all) — calling `/identity/whoami` for the startup check,
  `/backend/authenticate`/`/backend/deauthenticate` around the hotkey
  toggle, starting/stopping the voice-state subscription so Voice Mode and
  Backend Mode never both hold it at once, and a UX-only elevation-expiry
  poll (the real enforcement is server-side; see below). **This is fully
  unit tested** — 20 tests in `InterfaceShellViewModelTests.cs` drive the
  entire section-3 sequence (boot → real device check → VoiceMode →
  hotkey → real PIN auth against a fake server → BackendMode → same
  hotkey → real revocation call → VoiceMode again) against a
  `FakeHttpMessageHandler`, exactly the same principle every other test in
  this codebase uses: the real `InterfaceShellViewModel` code runs
  unmodified, only the network boundary is faked.
- **A real event-driven voice-state push**, closing the "never polling"
  requirement between the WPF shell and aura_core: `GET
  /voice/state/stream` (new, `core/src/aura_core/api/app.py`) is a
  Server-Sent-Events endpoint that pushes a new event only when the
  registry's `voice.session_state` actually changes, not on a fixed
  client-visible interval. `AuraApiClient.StreamVoiceStateAsync` consumes
  it with the same streaming-reader pattern `ChatStreamAsync` already
  used, and `VoiceModeViewModel` maps each real state
  (`Idle`/`ListeningForWake`/`Awake`/`Processing`/`Speaking`, exactly
  `AuraVoice.Core.VoiceState`'s values) into what the orb shows, reporting
  `Offline` honestly (with an automatic reconnect loop) if the stream
  drops rather than freezing on the last-known state. 5 Python tests (the
  underlying `voice_state_events` async generator, driven directly with
  `asyncio.wait_for`/`aclose()` rather than through `TestClient`, because
  this project's synchronous `TestClient` transport runs an ASGI call to
  full completion before returning anything and cannot exercise an
  endpoint that streams forever — see that test file's docstring) plus 4
  new C# tests (`VoiceModeViewModelTests.cs`).
- **`GET /identity/whoami`** (new) is the real substitute this build has
  for a production startup authentication screen. No Windows Hello or
  other hardware-backed factor is wired up anywhere in this codebase, so
  rather than inventing a separate, weaker check just for the boot screen,
  `AuthenticateAsync` answers "is the owner present" the same way every
  other trust decision here already does: a valid `X-Aura-Device-Token`.
  This is real and tested (5 Python tests, 3 C# client tests), but it is
  explicitly a lesser bar than the "owner authentication" language in the
  original request implies — it proves "this is a trusted device," not
  "a specific person is at the keyboard right now." Closing that gap
  requires an actual Windows Hello / biometric integration, which remains
  unbuilt (see below).

## Still not built, and why

- **Any real interactive owner-presence factor for the startup screen
  beyond device trust** (Windows Hello, PIN-at-launch, a trusted-device
  proximity check). `identity/whoami`'s device-token check is what exists
  and is tested; it is honestly weaker than "the owner personally
  authenticated just now." `BackendElevationService`'s PIN factor is
  reserved for backend elevation specifically, and reusing it as the
  startup factor too was deliberately avoided — this document does not
  pretend that substitution is equivalent to the biometric factor the
  original request describes.
- **Real microphone capture, device enumeration, echo cancellation, noise
  suppression, Bluetooth/default-device-change handling, and the actual
  gating of audio hardware by mute state.** `VoiceModeViewModel.SetMuted`
  only changes what the WPF UI displays; nothing in this codebase gates a
  real audio capture pipeline based on it, because `AuraVoice.Windows`'s
  microphone source (`NAudioMicrophoneSource`) has no privacy-gating hook
  built yet. Calling the current mute toggle a security control would be
  a false claim — it is a UI affordance only, documented as such directly
  in `VoiceModeViewModel`'s class comment.
- **Barge-in reflected in the WPF UI.** `AuraVoice.Core.VoiceSessionController.OnBargeIn()`
  exists and is tested at the state-machine level, and `VoiceModeView`
  will show `Speaking` → `Awake` when it fires (since that's a real state
  transition pushed through the same stream), but there is no distinct
  visual treatment for "the owner just interrupted AURA" versus an
  ordinary state change — both render identically as the state simply
  changing.
- **Task lifecycle surviving a Voice ⇄ Backend Mode switch as a
  UI-observable guarantee.** The Action Broker and task queue already run
  server-side, independent of any UI's lifetime, so a long-running task
  structurally cannot be affected by which WPF view happens to be visible
  — but there is no test in this pass that specifically proves a task
  started in one mode is still visibly progressing after a mode switch,
  because Backend Mode's Diagnostics/Tasks views don't yet expose
  in-flight task state at all (only diagnostics and audit history).
- **The literal Windows acceptance sequence** (start → authenticate →
  Voice Mode → speak → hotkey → PIN → Backend Mode → hotkey → Voice Mode,
  run on a real machine with a real microphone, speaker, and keyboard).
  Every server-side precondition it depends on is real and tested (the
  elevation boundary, the audit trail, the state machine's transition
  rules, the voice-to-execution wiring, the event-driven state push); the
  WPF-only glue that wires those preconditions into an actual running
  window (everything named in "what changed this pass" above) is now
  written but has literally never run. See the ACCEPTANCE TEST section of
  the final report for the honest per-step status.
- **Regating every existing device-token-gated endpoint behind backend
  elevation.** Unchanged from the previous pass: only `/backend/diagnostics`
  and `/backend/audit` require elevation. Endpoints Voice Mode legitimately
  needs during normal operation were deliberately left on the existing
  device-trust boundary.
- **Installer/updater integration** (packaging the new WPF assemblies,
  preserving identity/PIN/trusted-device state across an update). Not
  attempted this pass — see `install/` for the existing installer, which
  has not been modified to reference the new views/hotkey/session-monitor
  files.

## Hotkey collision audit

Unchanged from the previous pass. Chosen default: **`Ctrl+Alt+Shift+A`**,
centralized in `aura_core.config.Settings.backend_toggle_hotkey` (env
override: `AURA_BACKEND_TOGGLE_HOTKEY`) and served to the shell via the
ungated `GET /interface/config` endpoint — never hardcoded in UI code, and
now actually consumed by `MainWindow.xaml.cs`'s `RegisterHotkeyAsync` via
`HotkeyDefinition.Parse` before being handed to `Win32HotkeyManager.Register`.

Audited against, from training-data knowledge of each surface's documented
default bindings (not verified against a live instance of each product in
this sandbox — flagged honestly):

| Surface | Relevant defaults | Collision? |
|---|---|---|
| Windows shell | `Win+*` (task switching, snap, settings flyouts), `Alt+Tab`, `Ctrl+Alt+Del`/`Ctrl+Shift+Esc`, `Ctrl+Alt+Arrow` (some GPU driver rotate shortcuts) | No — none use the 3-modifier `Ctrl+Alt+Shift` combination without also involving `Win` |
| Browsers (Chrome/Firefox/Edge) | `Ctrl+Shift+<letter>` for various panels (e.g. `Ctrl+Shift+J` DevTools console, `Ctrl+Shift+N` incognito); none documented at `Ctrl+Alt+Shift+<letter>` | No |
| IDEs (VS Code, Visual Studio, JetBrains) | Heavy use of `Ctrl+K <key>` chords and `Ctrl+Shift+<letter>`; `Ctrl+Alt+<letter>` used sparingly; no common default at `Ctrl+Alt+Shift+A` specifically | No known collision, though a specific IDE extension could theoretically rebind it — flagged as a residual risk, not eliminated |
| Accessibility (Narrator, Magnifier, high contrast) | Narrator: `Ctrl+Win+Enter`; Magnifier: `Win+=`/`Win+-`; High contrast toggle: `Left Alt+Left Shift+PrtScn`; sticky/toggle/filter keys: repeated modifier presses, not a fixed combo | No — high contrast's combo uses PrtScn, not `A`, and is left-modifier-specific, not the same chord |
| AURA's own existing registrations | `Win32HotkeyManager` registers exactly one hotkey, only this one, only once per process | No collision, nothing else to conflict with |

**What this audit is, and isn't**: a documented reasoning pass against each
surface's commonly-published default bindings. It is not a live collision
test against a running Windows machine with every listed application
installed — that requires real Windows hardware this sandbox doesn't have.
The configuration is centralized specifically so a real collision found
during actual Windows commissioning is a one-line config change
(`AURA_BACKEND_TOGGLE_HOTKEY`), not a code change, and `Win32HotkeyManager`
already surfaces `HotkeyRegistrationStatus.AlreadyInUse` distinctly if
`RegisterHotKey` reports the combination is taken.

## Summary

The real security boundary Backend Mode depends on is built and enforced
at the API layer independent of any UI. The state machine that decides
which screen is shown is built and exhaustively tested. The WPF shell that
wires both of those into an actual running application — the mode-driven
window, the four real views, the Win32 hotkey registration, and the
Windows session-lock handling — is now written, believed correct after
careful manual review, and has never been compiled or run, because this
sandbox cannot do either for a `UseWPF` project. That gap is named
explicitly everywhere above and in the final report's ACCEPTANCE TEST
section, rather than being narrated as done.
