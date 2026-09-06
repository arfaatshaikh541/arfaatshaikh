# AURA Windows Shell

A native WPF desktop shell for AURA, talking to the real `aura_core` API
server (`/core`) over HTTP/SSE. Split into two projects deliberately:

- **`AuraShell.Core`** — plain `net8.0` class library. All the actual
  logic: the API client (including real SSE-stream parsing), and the
  view-models (`ChatViewModel`, `StatusViewModel`, `ApprovalsViewModel`,
  `MainViewModel`). Zero WPF-specific types. This is what's genuinely
  built and tested in this session.
- **`AuraShell`** — the WPF application itself (`App.xaml`,
  `MainWindow.xaml` + code-behind). Thin: it only wires up
  `AuraApiClient` → `MainViewModel` → data-bound XAML. This is real,
  carefully-written source, but **unverified** — see below.

## What's genuinely verified (this session, in a cloud Linux container)

```
cd AuraShell.Core.Tests && dotnet test
```

**13 tests, all passing.** They exercise `AuraShell.Core` against a fake
`HttpMessageHandler` (the C# equivalent of pointing the Python side's
`OllamaProvider` at an unreachable host — real code, fake network layer),
covering:

- Real SSE parsing: a multi-event `text/event-stream` body is decoded into
  the correct ordered sequence of `lane` → `chunk` → `chunk` → `done`
  events.
- `/status`, `/approvals`, `/approvals/{id}/decide`, `/audit/verify`,
  `/kill-switch/engage` all send the correct HTTP method/path/body and
  parse the response correctly, including snake_case JSON fields mapping
  to PascalCase C# properties.
- `ChatViewModel` builds its transcript incrementally as chunks arrive,
  clears input after send, and does nothing for blank input (no wasted
  network call).
- `ApprovalsViewModel.ApproveCommand` is disabled with nothing selected,
  and approving calls the real decide endpoint with `approved: true`,
  then refreshes.
- Connection failure (`HttpRequestException`) is handled, not thrown
  through to the caller, in `IsHealthyAsync`.

`AuraShell.Core` alone also builds cleanly: `cd AuraShell.Core && dotnet build`.

## What is NOT verified, and why

**The `AuraShell` WPF project cannot be built in this environment at
all.** It targets `net8.0-windows` with `UseWPF=true`, which requires the
Windows Desktop SDK — confirmed by actually attempting the build here:

```
error MSB4019: The imported project ".../Microsoft.NET.Sdk.WindowsDesktop.targets" was not found.
```

That failure happens at the very first MSBuild import step, before XAML
compilation even starts. So beyond "the `.csproj` and file structure are
well-formed enough that restore succeeds," **the XAML markup itself has
never been compiled or run.** No window has ever appeared. No binding has
ever been exercised against a live `DataContext`. Treat `App.xaml`,
`MainWindow.xaml`, and their code-behind as a careful first draft, not as
tested software, until you build it on Windows.

## Building and running it for real (on your Windows machine)

Prerequisites: Windows 10/11, [.NET 8 SDK](https://dotnet.microsoft.com/download)
with the Windows Desktop workload (installed by default on Windows).

```powershell
cd apps\windows
dotnet build                      # builds all three projects, including the WPF shell, for the first time anywhere
dotnet test AuraShell.Core.Tests  # re-confirm the 13 tests still pass on your machine
```

Start the core API server (see `core/RUNBOOK.md`), then run the shell:

```powershell
$env:AURA_CORE_URL = "http://localhost:8000"   # optional, this is the default
dotnet run --project AuraShell
```

You should see a window with three tabs (AURA / Status / Approvals) and a
kill-switch toggle in the top bar. If the core server isn't running, the
Status tab will show `UNAVAILABLE`/`NOT_CONNECTED` rows rather than the
app crashing — that's the intended fail-soft behavior, but confirming it
actually behaves that way on Windows is still an open item.

## Known gaps, explicitly

- No packaging/installer yet (`dotnet publish`, MSIX, or the installer
  requirements in the original brief — none attempted).
- No app icon, no dark/light theme handling beyond the hardcoded top bar
  color, no window-state persistence.
- The chat transcript is a flat `ObservableCollection<string>` — fine for
  a first real version, not a rich chat UI (no markdown, no per-message
  styling).
- No voice integration yet — see `apps/voice/README.md`.
- No local computer-control, telephony, or connector UI — those
  capabilities don't exist server-side yet either (see
  `core/src/aura_core/status.py`'s seeded `NOT_CONNECTED` entries).
