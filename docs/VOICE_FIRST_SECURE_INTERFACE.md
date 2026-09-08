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
There is also no Windows machine reachable from this session at all —
checked directly (the only environment available is another Linux cloud
sandbox) — so "build it on Windows," "run the native hotkey/session
tests," and "run the full acceptance sequence" are not things more effort
inside this session can produce; they require a person with a real
Windows machine to run `WINDOWS-COMMISSIONING.ps1` (updated this pass —
see below) and report back. What *has* changed, across this pass and the
one before it: every WPF-only source file (bootstrap, the four views, the
Win32 hotkey manager, the Windows session monitor, the owner-presence
credential dialog) now exists, is written against the already-tested
`AuraShell.Core` contracts, and is believed correct after careful manual
review (XAML well-formedness checked with an XML parser; every `.cs`
file's braces balanced; every type/namespace/method reference
cross-checked by hand against the real APIs it calls; the two PowerShell
scripts this pass touched were parsed with PowerShell 7's own
`[System.Management.Automation.Language.Parser]` — genuinely available in
this sandbox — confirming zero syntax errors, real verification rather
than a guess). None of it has been **compiled, run, or visually
verified**, because nothing in this sandbox can do that for a `UseWPF`
project or a real Windows session. Treat every WPF-only file below as
"written carefully, not proven" until a real Windows build and a real run
of `WINDOWS-COMMISSIONING.ps1` confirm it.

## Production-blocker close-out pass (this pass)

Four things named as remaining gaps after the previous pass are now
addressed as far as this sandbox allows -- real code and real tests where
testable on Linux, honestly flagged as unverified where they aren't:

- **Real microphone privacy gating.** `AuraVoice.Core.VoicePrivacyGate`
  (new, pure, fully unit-tested -- 4 tests) is the real behavioral
  distinction between FULL_MIC_OFF and WAKE_WORD_ONLY: FullMicOff must
  physically close the hardware, WakeWordOnly keeps it open and running
  the wake-word detector but discards a hit rather than escalating it
  into a command. `WindowsVoicePipeline` (AuraVoice.Windows, builds on
  Linux, confirmed with a real `dotnet build` against the real NAudio
  API) wires this gate to the real `NAudioMicrophoneSource.Start()`/
  `Stop()` calls and to the wake-word branch of its frame-processing
  loop. `AuraVoice.Windows.Host/Program.cs` polls aura_core's new
  `GET /voice/privacy` every second and applies real changes to the
  gate, logging every transition. The WPF shell's Voice Mode view now
  has two toggles (Mute -> FullMicOff, Wake-word only -> WakeWordOnly,
  mutually exclusive), each pushing the real mode via a new
  `POST /voice/privacy` (6 new Python tests) and
  `AuraApiClient.SetVoicePrivacyAsync`/`GetVoicePrivacyAsync` (2 new C#
  client tests, 3 new `VoiceModeViewModel` tests proving the push and the
  mutual exclusion). **Never run against a real microphone** -- the gate
  logic and the wiring are real and tested/reviewed; the actual hardware
  behavior needs Windows.
- **Audio-device resilience.** `NAudioMicrophoneSource` now makes
  `Start()`/`Stop()` idempotent and reacts to NAudio's own
  `RecordingStopped` event: a deliberate stop is distinguished from a
  real device loss (unplugged, Bluetooth dropout, driver reset,
  default-device change invalidating the open handle), and a real loss
  triggers an automatic reopen with capped exponential backoff (500ms up
  to 30s, never gives up permanently). An explicit `Start()`/`Stop()`
  call always supersedes an in-flight automatic reopen via a
  cancellation token, closing a real race where a stale reopen could
  otherwise switch the microphone back on after the owner (or a privacy
  mode change) explicitly asked for it to be off. `DeviceLost`/
  `DeviceRecovered` events are logged by `AuraVoice.Windows.Host`. **Not
  built**: explicit default-device-change detection via
  `MMDeviceEnumerator`, sample-rate renegotiation across devices, and
  Bluetooth-specific quirks -- these need real hardware to get right and
  are not claimed here.
- **A real additional owner-presence factor at startup.**
  `InterfaceShellViewModel.OwnerPresenceCheck` (new: `Func<Task<bool>>?`,
  null by default so every existing test is unaffected -- 4 new tests
  prove the gate) runs *before* the device-token check in
  `AuthenticateAsync`, and fails closed (including on an exception from
  the check itself, never propagated). The WPF host wires this to a real
  Windows credential prompt: `WindowsOwnerPresenceVerifier` (new, WPF
  project) calls the standard `LogonUser` Win32 API against the
  *current* Windows account's password -- a single long-stable,
  extensively documented primitive, deliberately chosen over a WinRT/UWP
  Windows Hello projection this sandbox has no way to verify the exact
  binding shape of. This is still explicitly **not Windows Hello** (no
  biometric or hardware-backed factor) -- it is a genuine "does the
  person at the keyboard know this account's password right now" check,
  shown via a new modal `OwnerPresenceDialog` window before
  `AuthenticationView`'s device-token screen ever runs.
- **Installer integration.** `install/Install-AURA.ps1` now preserves the
  device-token directory (`core\.aura\`) across an update alongside the
  existing DB/`.models` preservation -- without this fix, every update
  would have silently forced re-enrollment, since that file lives inside
  the directory the installer replaces. It also now runs
  `dotnet test` for both C# test projects (not just `dotnet build`) as
  part of its self-test gate. `WINDOWS-COMMISSIONING.ps1` gained an
  automated `/identity/whoami` + `/interface/config` + `/voice/privacy`
  round-trip check, and a new interactive "voice-first shell walkthrough"
  section that launches the real `AuraShell.exe` against the script's
  own throwaway `aura_core` server and walks the operator through the
  exact section-3 sequence (owner-presence prompt -> Voice Mode, no
  dashboard -> hotkey -> PIN challenge -> Backend Mode -> same hotkey ->
  Voice Mode again -> OS lock revokes elevation), self-reported per step
  since WPF window content isn't observable from a script. Both scripts
  were verified with PowerShell's own parser (zero syntax errors) but,
  like everything else in this section, **never executed** -- there is no
  Windows machine anywhere in this session to run them on.

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

- **Windows Hello / biometric authentication specifically.** This pass
  added a real interactive owner-presence factor
  (`WindowsOwnerPresenceVerifier`, a `LogonUser` credential prompt run
  before the device-token check) that is a genuine step beyond "device
  trust alone," but it is still not a hardware-backed or biometric
  factor. `BackendElevationService`'s PIN factor remains reserved for
  backend elevation specifically, not reused as the startup factor. A
  true Windows Hello integration (via the WinRT
  `Windows.Security.Credentials.UI` API) was deliberately not attempted:
  it requires WinRT/CsWinRT projections this sandbox has no way to
  compile-check or verify the exact binding shape of, and getting subtle
  interop details wrong while totally unable to test them was judged a
  worse outcome than a clearly-labeled, lower-tech-but-verifiable
  alternative using a single long-stable Win32 API.
- **Echo cancellation, explicit default-device-change detection, and
  Bluetooth-specific quirks.** `NAudioMicrophoneSource` now has real
  device-loss detection and automatic reopen with backoff (see the
  close-out section above), which covers "the mic disappeared and came
  back." It does NOT do acoustic echo cancellation, explicit
  `MMDeviceEnumerator`-based default-device-change callbacks, or
  Bluetooth-codec-specific handling (e.g. a Bluetooth headset switching
  profiles mid-call) -- these need real hardware and a real Bluetooth
  device to get right, and are not claimed here.
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
- **Installer/updater integration beyond the device-token-preservation
  fix above.** Packaging itself needed no change -- `Install-AURA.ps1`'s
  `dotnet build "$StagingDir\apps\windows\AuraShell.sln"` already builds
  every file in the project, including the new views/hotkey/session-
  monitor/owner-presence files, since staging is a full directory copy
  before that build runs. What remains unaddressed: no MSIX/single-file
  packaging, no auto-update mechanism, no code-signing, and no rollback
  test that has ever actually executed (the rollback *logic* exists and
  is reviewed, but only a real failed install on Windows would prove it
  fires correctly).

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
