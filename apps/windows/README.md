# AURA Windows Shell

A native WPF desktop shell for AURA, talking to the real `aura_core` API
server (`/core`) over HTTP/SSE. Split into two projects deliberately:

- **`AuraShell.Core`** — plain `net8.0` class library. All the actual
  logic: the API client (including real SSE-stream parsing), the
  application-level security/interface state machine
  (`InterfaceModeManager`), the composition root that wires it all
  together (`InterfaceShellViewModel`), and the view-models
  (`ChatViewModel`, `StatusViewModel`, `ApprovalsViewModel`,
  `MainViewModel`, `VoiceModeViewModel`). Zero WPF-specific types (no
  `System.Windows.Controls`, no P/Invoke). This is what's genuinely built
  and tested — 83 tests, all passing on a clean Linux `dotnet test`.
- **`AuraShell`** — the WPF application itself (`App.xaml`,
  `MainWindow.xaml` + `Views/*.xaml`, `Win32HotkeyManager.cs`,
  `SystemSessionMonitor.cs`). This is real, carefully-written source, but
  **unverified** — see below.

## The voice-first shell: what launches by default

`App.xaml.cs` does **not** show a prebuilt dashboard. It shows exactly one
window (`MainWindow`), whose content is driven entirely by
`InterfaceShellViewModel.Mode` (`AuraShell.Core.InterfaceModeManager`),
starting at `Booting` on every single launch:

```
Booting -> AuthRequired -> Authenticating -> VoiceMode <-> BackendAuthRequired -> BackendAuthenticating -> BackendMode
                                                |                                                              |
                                             Locked  <-------------------------------------------------------+
                                                |
                                          ErrorRecovery
```

Four views correspond to that state machine, swapped in `MainWindow.xaml.cs`'s
`ApplyView`:

| Mode(s) | View | What it shows |
|---|---|---|
| Booting, AuthRequired, Authenticating, Locked, ErrorRecovery | `Views/AuthenticationView.xaml` | A single centered status line, plus a Retry/Recover button only when there's something to act on. This is the real production startup screen — see "the real substitute for Windows Hello" below. |
| VoiceMode | `Views/VoiceModeView.xaml` | One central orb whose color/label reflect the real voice-session state, pushed live from aura_core's `/voice/state/stream`. No sidebar, no transcript, no tables. A mute toggle (UI-visible-only — see Known gaps). |
| BackendAuthRequired, BackendAuthenticating | `Views/BackendChallengeView.xaml` | The real second-factor PIN prompt the hotkey opens. A `PasswordBox`, never a visible text field. |
| BackendMode | `Views/BackendModeView.xaml` | Where the old dashboard's Chat/Status/Approvals tabs and the kill switch now live, plus new Diagnostics and Audit Trail tabs backed by real `/backend/diagnostics`/`/backend/audit` data. Reachable only through the hotkey + PIN challenge; leaving it (same hotkey) revokes the elevation token and clears this data, not just hides it. |

The default backend-toggle hotkey (`Ctrl+Alt+Shift+A`, centralized in
`aura_core`'s `/interface/config`, never hardcoded here) is registered by
`Win32HotkeyManager` once the window has a real HWND
(`MainWindow.xaml.cs`'s `SourceInitialized` handler). Pressing it from
`VoiceMode` opens the PIN challenge; pressing it again from `BackendMode`
revokes elevation and returns to `VoiceMode` immediately, no re-auth
required to leave. `SystemSessionMonitor` listens for real Windows
lock/unlock/logoff/sleep/resume notifications and revokes elevation on
lock/sleep the same way the hotkey's exit path does — Backend Mode never
survives an OS lock.

See `docs/VOICE_FIRST_SECURE_INTERFACE.md` (repo root) for the full,
section-by-section account of what's real, tested, and still unverified
in this design.

### The real substitute for Windows Hello

There is no biometric or hardware-backed owner-presence factor wired up
anywhere in this codebase. The startup screen answers "is the owner
present" the same way every other trust decision in this codebase already
does — a valid `X-Aura-Device-Token`, checked via `GET /identity/whoami`.
That is a real, tested check, but it proves "this is a trusted device,"
not "a specific person is at the keyboard right now" — treat it as
honestly weaker than the Windows Hello language in the original design
brief until a real biometric factor is added.

## What's genuinely verified (this session, in a cloud Linux container)

```
cd AuraShell.Core.Tests && dotnet test
```

**83 tests, all passing.** They exercise `AuraShell.Core` against a fake
`HttpMessageHandler` (the C# equivalent of pointing the Python side's
`OllamaProvider` at an unreachable host — real code, fake network layer)
and, for `InterfaceShellViewModel`, drive the *entire* voice-to-backend-
and-back sequence end to end against that fake server. Coverage includes:

- Real SSE parsing for both `/chat` and the new `/voice/state/stream`: a
  multi-event stream is decoded into the correct ordered sequence of
  events, including a genuine reconnect-on-disconnect loop
  (`VoiceModeViewModel`) that reports `Offline` rather than freezing.
- `InterfaceModeManager`'s full state machine (15 tests): the hotkey's
  asymmetric entering-needs-auth/leaving-doesn't behavior, elevation
  expiring while Backend Mode is open routing back through
  `BackendAuthRequired` rather than straight to `VoiceMode`, invalid
  transitions throwing, and `ModeChanged` firing exactly once per real
  transition.
- `Win32HotkeyManager`'s *testable* half — `HotkeyDefinition` parsing and
  `HotkeyDebouncer`'s clock-injectable dedup logic (13 tests) — proving
  20 rapid simulated presses inside the debounce window fire a handler
  exactly once. The actual `RegisterHotKey`/`WM_HOTKEY` P/Invoke code
  itself is untestable without a real Win32 window; see below.
- `InterfaceShellViewModel` (20 tests): the full boot → real device check
  → VoiceMode → hotkey → real PIN authentication → BackendMode → same
  hotkey → real revocation call → VoiceMode sequence, plus a wrong-PIN
  path that never says which factor failed, an OS-lock path that revokes
  elevation before locking, an unlock path that always re-authenticates
  from scratch (never restores Backend Mode), and a fast-polling
  elevation-expiry test proving the shell notices a server-side-expired
  session even with the UI otherwise idle.
- `/status`, `/approvals`, `/approvals/{id}/decide`, `/audit/verify`,
  `/kill-switch/engage`, `/backend/authenticate|deauthenticate|session|
  diagnostics|audit`, `/identity/whoami`, `/interface/config` all send the
  correct HTTP method/path/headers/body and parse the response correctly.

`AuraShell.Core` alone also builds cleanly: `cd AuraShell.Core && dotnet build`.

## What is NOT verified, and why

**The `AuraShell` WPF project cannot be built in this environment at
all.** It targets `net8.0-windows` with `UseWPF=true`, which requires the
Windows Desktop SDK — confirmed by actually attempting the build here,
every time it's been tried this session:

```
error MSB4019: The imported project ".../Microsoft.NET.Sdk.WindowsDesktop.targets" was not found.
```

That failure happens at the very first MSBuild import step, before XAML
compilation even starts. So beyond "the `.csproj` and file structure are
well-formed enough that restore succeeds" and "every `.xaml` file parses
as well-formed XML" (checked by hand with a plain XML parser, since no
XAML compiler is available), **none of it has ever been compiled or run.**
No window has ever appeared. No binding has ever been exercised against a
live `DataContext`. `Win32HotkeyManager` has never called a real
`RegisterHotKey`. `SystemSessionMonitor` has never received a real
`WM_WTSSESSION_CHANGE`. Treat every file under `AuraShell/` (not
`AuraShell.Core/`) as a careful, cross-checked draft, not as tested
software, until you build and run it on Windows.

## Building and running it for real (on your Windows machine)

Prerequisites: Windows 10/11, [.NET 8 SDK](https://dotnet.microsoft.com/download)
with the Windows Desktop workload (installed by default on Windows).

```powershell
cd apps\windows
dotnet build                      # builds all three projects, including the WPF shell, for the first time anywhere
dotnet test AuraShell.Core.Tests  # re-confirm the 83 tests still pass on your machine
```

Start the core API server (see `core/RUNBOOK.md`), then run the shell:

```powershell
aura serve   # binds a Unix domain socket, e.g. C:\Users\you\.aura\core.sock
$env:AURA_CORE_SOCKET = "C:\Users\you\.aura\core.sock"   # path aura serve printed
dotnet run --project AuraShell
```

`AURA_CORE_SOCKET` is the "local, not localhost" transport section 7 asks
for (see `core/src/aura_core/ipc.py`) and takes priority when set. If it's
unset, the shell falls back to loopback TCP via `AURA_CORE_URL` (default
`http://localhost:8000`, matching `aura serve --host`) — useful for local
dev tooling that only speaks HTTP-over-TCP.

Once an owner has enrolled (`aura enroll`) and this machine has a valid
`AURA_DEVICE_TOKEN`, you should see the authentication screen briefly
("Verifying this device…") and then land directly in Voice Mode — a
single dark screen with a central orb, no dashboard, no tabs. Press the
configured hotkey to reach the PIN challenge and, on success, Backend
Mode's tabs (this is the same tab layout the previous version showed by
default; it now requires the hotkey + PIN to reach). If the core server
isn't running, the authentication screen will show an honest error
instead of the app crashing or hanging — confirming that behavior on a
real Windows machine is still an open item, exactly like everything else
in this section.

## Known gaps, explicitly

- **The mute toggle in Voice Mode is UI-visible-only.** It does not gate
  any real audio capture pipeline — `AuraVoice.Windows`'s microphone
  source has no privacy-gating hook built yet. Do not treat it as a
  privacy control until that's wired up.
- **No hardware-backed owner-presence factor at startup** (Windows Hello,
  biometrics) — see "the real substitute for Windows Hello" above.
- **No installer/updater integration yet** (`dotnet publish`, MSIX, or
  the installer requirements in the original brief — none attempted; see
  `install/` for the existing, unmodified installer).
- **No app icon, no dark/light theme handling** beyond the hardcoded dark
  palette, no window-state persistence.
- **Barge-in has no distinct visual treatment** in Voice Mode — it renders
  as an ordinary state transition (Speaking → Awake), same as any other.
- **Backend Mode's Diagnostics tab does not yet show in-flight task
  state** — only audit-chain validity, recent Security Guardian events,
  and capability status. Task/Goal views described in the original
  design brief are not built.
- No local computer-control, telephony, or connector UI beyond what
  already existed — those capabilities don't exist server-side yet either
  (see `core/src/aura_core/status.py`'s seeded `NOT_CONNECTED` entries).
