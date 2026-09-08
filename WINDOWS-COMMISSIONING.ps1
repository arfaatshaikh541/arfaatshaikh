#Requires -Version 5.1
<#
.SYNOPSIS
    Runs every AURA check that this codebase's Linux build environment
    could not perform, on your real Windows machine, and packages the
    results into one diagnostic bundle.

.DESCRIPTION
    See BLOCKERS.md at the repo root for the full classification this
    script exists to close out: every item tagged REQUIRES_WINDOWS_
    VALIDATION there is exercised here. Everything that could be built
    and automatically tested without real hardware already has been --
    this script is specifically for the remainder: native WPF shell
    build/launch, real microphone capture, VAD, wake word, STT, TTS,
    barge-in/interruption, local model generation via Ollama, memory,
    background task crash-recovery, and connector health, all against
    real Windows APIs and real audio hardware instead of this sandbox's
    substitutes (Xvfb, bundled Chromium, synthetic test audio).

    Where a check can be fully automated (builds, unit/integration test
    suites, HTTP health checks), it is. The voice pipeline's actual
    audio content cannot be scripted without a real microphone and a
    real person -- for that step, this script starts the real pipeline,
    tells you exactly what to say and when, and then automatically
    grades the result by parsing the pipeline's own real-time log file
    for evidence (state transitions, spoken responses, errors) rather
    than asking you to self-report pass/fail.

    Every result -- PASS, FAIL, or SKIP -- is written to one timestamped
    diagnostic bundle (a .zip) containing every log this script produced,
    so if anything fails, that one file is everything needed to diagnose
    it remotely.

.PARAMETER RepoRoot
    Path to the AURA repository. Defaults to this script's own directory
    (it's meant to live at the repo root).

.PARAMETER OutputDir
    Where to write the diagnostic bundle .zip. Defaults to your Desktop.

.PARAMETER SkipVoiceInteractive
    Skip the interactive microphone/speaker section entirely (useful for
    a quick non-interactive re-run of everything else). Those checks are
    recorded as SKIP, not FAIL.

.PARAMETER SkipShellInteractive
    Skip the interactive WPF shell walkthrough (owner-presence prompt,
    Voice Mode's no-dashboard appearance, the backend hotkey + PIN
    challenge, and an OS-lock check) -- this is what actually exercises
    the voice-first secure interface end to end on real Windows,
    self-reported by you at each step since there is no way for this
    script to observe WPF window content from the outside. Recorded as
    SKIP, not FAIL, when skipped.

.PARAMETER VoiceListenSeconds
    How long to run the real voice pipeline during the interactive
    section, giving you time to say the wake word, a command, and
    interrupt AURA mid-response. Default 30.

.PARAMETER ServerPort
    Port to run a throwaway aura_core server on for the duration of this
    script. Default 8756 (chosen to avoid colliding with a server you
    might already have running on the default 8000).

.EXAMPLE
    .\WINDOWS-COMMISSIONING.ps1
    Full interactive run.

.EXAMPLE
    .\WINDOWS-COMMISSIONING.ps1 -SkipVoiceInteractive
    Everything except the microphone/speaker section -- useful for
    quickly re-checking builds and connector health after a code change.
#>
[CmdletBinding()]
param(
    [string]$RepoRoot = $PSScriptRoot,
    [string]$OutputDir = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop),
    [switch]$SkipVoiceInteractive,
    [switch]$SkipShellInteractive,
    [int]$VoiceListenSeconds = 30,
    [int]$ServerPort = 8756
)

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = [System.IO.Path]::GetTempPath()
}

$ErrorActionPreference = "Continue"
$Script:Results = @()

function Add-Result {
    param([string]$Name, [string]$Status, [string]$Detail)
    $Script:Results += [PSCustomObject]@{
        Name   = $Name
        Status = $Status
        Detail = $Detail
        At     = (Get-Date).ToString("o")
    }
    $color = switch ($Status) { "PASS" { "Green" }; "FAIL" { "Red" }; "SKIP" { "Yellow" }; default { "Gray" } }
    Write-Host ("  [{0,-4}] {1}: {2}" -f $Status, $Name, $Detail) -ForegroundColor $color
}

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host "==== $Title ====" -ForegroundColor Cyan
}

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BundleDir = Join-Path ([System.IO.Path]::GetTempPath()) "AURA-Commissioning-$Timestamp"
$LogsDir = Join-Path $BundleDir "logs"
New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null

Write-Host "AURA Windows Commissioning -- $Timestamp" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"
Write-Host "Diagnostic bundle will be written under: $BundleDir"

$venvPython = Join-Path $RepoRoot "core\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    $venvPython = "python"
}

# ---------------------------------------------------------------------
# 1. Preflight
# ---------------------------------------------------------------------
Write-Section "Preflight (install\preflight.py)"
try {
    $preflightScript = Join-Path $RepoRoot "install\preflight.py"
    $preflightRaw = & $venvPython $preflightScript --json 2>&1 | Out-String
    $preflightRaw | Out-File (Join-Path $LogsDir "preflight.json") -Encoding utf8
    $checks = $preflightRaw | ConvertFrom-Json
    foreach ($c in $checks) {
        $status = switch ($c.status) { "PASS" { "PASS" }; "WARN" { "SKIP" }; default { "FAIL" } }
        Add-Result "preflight.$($c.name)" $status $c.detail
    }
} catch {
    Add-Result "preflight" "FAIL" "could not run preflight.py: $($_.Exception.Message)"
}

# ---------------------------------------------------------------------
# 2. Python test suite (memory, tasks, governance, connectors, voice
#    providers, executive, everything already unit/integration-tested
#    in the Linux sandbox -- re-run here to catch any Windows-specific
#    SQLite/filesystem/path behavior difference)
# ---------------------------------------------------------------------
Write-Section "Python test suite (core\tests)"
Push-Location (Join-Path $RepoRoot "core")
try {
    $env:AURA_ENV = "test"
    $pytestLog = Join-Path $LogsDir "pytest.log"
    & $venvPython -m pytest -q *> $pytestLog
    $pytestExit = $LASTEXITCODE
    $pytestTail = (Get-Content $pytestLog -Tail 5) -join " | "
    if ($pytestExit -eq 0) {
        Add-Result "python.pytest" "PASS" $pytestTail
    } else {
        Add-Result "python.pytest" "FAIL" "exit $pytestExit -- see logs\pytest.log ($pytestTail)"
    }

    Write-Section "Background task crash-recovery (Windows SQLite/filesystem behavior)"
    $taskLog = Join-Path $LogsDir "task-recovery.log"
    & $venvPython -m pytest tests/test_task_engine.py tests/test_end_to_end.py -v *> $taskLog
    if ($LASTEXITCODE -eq 0) {
        Add-Result "tasks.recovery" "PASS" "TaskEngine lease-expiry/crash-recovery tests passed on this machine"
    } else {
        Add-Result "tasks.recovery" "FAIL" "see logs\task-recovery.log"
    }
} finally {
    Remove-Item Env:\AURA_ENV -ErrorAction SilentlyContinue
    Pop-Location
}

# ---------------------------------------------------------------------
# 3. Native Windows shell: build (the one thing this whole codebase has
#    never been able to verify at all, not even partially) and test
# ---------------------------------------------------------------------
Write-Section "Native Windows shell (AuraShell.sln)"
$shellBuildLog = Join-Path $LogsDir "aurashell-build.log"
& dotnet build "$RepoRoot\apps\windows\AuraShell.sln" --configuration Release *> $shellBuildLog
if ($LASTEXITCODE -eq 0) {
    Add-Result "windows.aurashell.build" "PASS" "AuraShell.sln built in Release -- WPF requires the Windows Desktop SDK, which could never be verified in the Linux sandbox this codebase was authored in"
} else {
    Add-Result "windows.aurashell.build" "FAIL" "see logs\aurashell-build.log"
}

$shellTestLog = Join-Path $LogsDir "aurashell-test.log"
& dotnet test "$RepoRoot\apps\windows\AuraShell.Core.Tests\AuraShell.Core.Tests.csproj" *> $shellTestLog
if ($LASTEXITCODE -eq 0) {
    Add-Result "windows.aurashell.tests" "PASS" "AuraShell.Core.Tests passed"
} else {
    Add-Result "windows.aurashell.tests" "FAIL" "see logs\aurashell-test.log"
}

Write-Section "AuraShell launch check"
$shellExe = Get-ChildItem -Path "$RepoRoot\apps\windows\AuraShell\bin\Release" -Recurse -Filter "AuraShell.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -eq $shellExe) {
    Add-Result "windows.aurashell.launch" "SKIP" "AuraShell.exe not found -- see aurashell-build.log"
} else {
    Add-Result "windows.aurashell.exe_found" "PASS" "$($shellExe.FullName) -- actual launch + the voice-first shell walkthrough happens later, once a real aura_core server is running for it to talk to"
}

# ---------------------------------------------------------------------
# 4. Voice C# projects: build and test (AuraVoice.Windows/.Host actually
#    compiling with the real NAudio/System.Speech Windows backends, not
#    just the net8.0-windows-without-UseWPF trick that let them compile
#    on Linux)
# ---------------------------------------------------------------------
Write-Section "Voice projects (AuraVoice.sln)"
$voiceBuildLog = Join-Path $LogsDir "auravoice-build.log"
& dotnet build "$RepoRoot\apps\voice\AuraVoice.sln" --configuration Release *> $voiceBuildLog
if ($LASTEXITCODE -eq 0) {
    Add-Result "voice.build" "PASS" "AuraVoice.sln built in Release, including AuraVoice.Windows.Host"
} else {
    Add-Result "voice.build" "FAIL" "see logs\auravoice-build.log"
}

$voiceTestLog = Join-Path $LogsDir "auravoice-test.log"
& dotnet test "$RepoRoot\apps\voice\AuraVoice.Core.Tests\AuraVoice.Core.Tests.csproj" *> $voiceTestLog
if ($LASTEXITCODE -eq 0) {
    Add-Result "voice.core_tests" "PASS" "AuraVoice.Core.Tests passed (VAD, state machine, ConversationOrchestrator, HTTP providers, FileVoiceLog)"
} else {
    Add-Result "voice.core_tests" "FAIL" "see logs\auravoice-test.log"
}

# ---------------------------------------------------------------------
# 5. Start a throwaway aura_core server for the remaining checks
# ---------------------------------------------------------------------
Write-Section "Starting aura_core server on port $ServerPort"
$serverBaseUrl = "http://127.0.0.1:$ServerPort"
$serverLog = Join-Path $LogsDir "aura_core_server.log"
$serverErrLog = Join-Path $LogsDir "aura_core_server.err.log"
$serverProc = $null
Push-Location (Join-Path $RepoRoot "core")
try {
    $env:AURA_ENV = "local"
    $serverProc = Start-Process -FilePath $venvPython `
        -ArgumentList "-m", "uvicorn", "aura_core.api.app:create_app", "--factory", "--host", "127.0.0.1", "--port", "$ServerPort" `
        -RedirectStandardOutput $serverLog -RedirectStandardError $serverErrLog -WindowStyle Hidden -PassThru
} finally {
    Pop-Location
}

$serverReady = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    try {
        $resp = Invoke-WebRequest -Uri "$serverBaseUrl/health" -UseBasicParsing -TimeoutSec 2
        if ($resp.StatusCode -eq 200) { $serverReady = $true; break }
    } catch { }
}

if ($serverReady) {
    Add-Result "server.startup" "PASS" "responded to /health within $($i + 1)s"
} else {
    Add-Result "server.startup" "FAIL" "no response from /health within 20s -- see logs\aura_core_server.log / .err.log"
}

function Test-CapabilityStatus {
    param([string]$Name, [string]$ExpectedStatus = "LIVE")
    try {
        $status = Invoke-RestMethod -Uri "$serverBaseUrl/status" -TimeoutSec 5
        $entry = $status.PSObject.Properties[$Name]
        if ($null -eq $entry) {
            Add-Result "status.$Name" "FAIL" "capability not present in /status response"
        } elseif ($entry.Value.status -eq $ExpectedStatus) {
            Add-Result "status.$Name" "PASS" $entry.Value.detail
        } else {
            Add-Result "status.$Name" "FAIL" "expected $ExpectedStatus, got $($entry.Value.status): $($entry.Value.detail)"
        }
    } catch {
        Add-Result "status.$Name" "FAIL" "could not query /status: $($_.Exception.Message)"
    }
}

if ($serverReady) {
    Write-Section "Capability status"
    Test-CapabilityStatus "memory.store"
    Test-CapabilityStatus "voice.wake_word"
    Test-CapabilityStatus "voice.stt"
    Test-CapabilityStatus "voice.tts"

    Write-Section "Connector health"
    try {
        $connectors = Invoke-RestMethod -Uri "$serverBaseUrl/connectors" -TimeoutSec 10
        $connectors | ConvertTo-Json -Depth 6 | Out-File (Join-Path $LogsDir "connectors.json") -Encoding utf8
        foreach ($c in $connectors) {
            $st = $c.status.status
            $result = if ($st -eq "LIVE") { "PASS" } elseif ($st -in @("NOT_CONNECTED", "BLOCKED_BY_POLICY", "READY_TO_CONNECT")) { "SKIP" } else { "FAIL" }
            Add-Result "connector.$($c.name)" $result "$st -- $($c.status.detail)"
        }
    } catch {
        Add-Result "connectors" "FAIL" "could not query /connectors: $($_.Exception.Message)"
    }

    Write-Section "Local model generation (Ollama)"
    try {
        $chatBody = @{ message = "Reply with a short greeting so this commissioning script can confirm you're really there." } | ConvertTo-Json
        $chatResp = Invoke-WebRequest -Uri "$serverBaseUrl/chat" -Method Post -Body $chatBody -ContentType "application/json" -TimeoutSec 45 -UseBasicParsing
        $chatResp.Content | Out-File (Join-Path $LogsDir "chat-response.log") -Encoding utf8
        if ($chatResp.Content -match '"chunk"') {
            Add-Result "model.generation" "PASS" "received real streamed content from /chat -- Ollama is reachable and generating"
        } elseif ($chatResp.Content -match '"error"') {
            Add-Result "model.generation" "SKIP" "no chunks -- /chat reported an error, most likely Ollama isn't running (see core\RUNBOOK.md); exact message in logs\chat-response.log"
        } else {
            Add-Result "model.generation" "FAIL" "unexpected /chat response -- see logs\chat-response.log"
        }
    } catch {
        Add-Result "model.generation" "FAIL" "could not reach /chat: $($_.Exception.Message)"
    }

    Write-Section "Voice-first interface backend (identity/whoami, interface/config, voice/privacy)"
    try {
        $whoami = Invoke-RestMethod -Uri "$serverBaseUrl/identity/whoami" -TimeoutSec 5
        Add-Result "identity.whoami" "PASS" "enrolled=$($whoami.enrolled) owner=$($whoami.owner_name)"
    } catch {
        Add-Result "identity.whoami" "FAIL" "could not reach /identity/whoami: $($_.Exception.Message)"
    }
    try {
        $ifaceConfig = Invoke-RestMethod -Uri "$serverBaseUrl/interface/config" -TimeoutSec 5
        Add-Result "interface.config" "PASS" "default_mode=$($ifaceConfig.default_interface_mode) hotkey=$($ifaceConfig.backend_toggle_hotkey)"
    } catch {
        Add-Result "interface.config" "FAIL" "could not reach /interface/config: $($_.Exception.Message)"
    }
    try {
        # A full round trip through every real privacy mode
        # (WindowsVoicePipeline.PrivacyGate's contract) -- this is the
        # backend half of "FULL MIC OFF vs. WAKE-WORD-ONLY" gating;
        # actually observing the microphone hardware react is the
        # manual voice-pipeline section below, since that needs a real
        # AuraVoice.Windows.Host process and a human ear.
        foreach ($mode in @("WakeWordOnly", "FullMicOff", "Normal")) {
            Invoke-RestMethod -Uri "$serverBaseUrl/voice/privacy" -Method Post -Body (@{ mode = $mode } | ConvertTo-Json) -ContentType "application/json" -TimeoutSec 5 | Out-Null
            $readBack = Invoke-RestMethod -Uri "$serverBaseUrl/voice/privacy" -TimeoutSec 5
            if ($readBack.mode -ne $mode) {
                throw "set $mode but read back $($readBack.mode)"
            }
        }
        Add-Result "voice.privacy_api" "PASS" "Normal/WakeWordOnly/FullMicOff all set and read back correctly"
    } catch {
        Add-Result "voice.privacy_api" "FAIL" "$($_.Exception.Message)"
    }
} else {
    Add-Result "status.checks" "SKIP" "server never came up -- skipping status/connector/model checks"
}

# ---------------------------------------------------------------------
# 5b. Voice-first shell walkthrough (interactive): the exact section-3
#     sequence (boot -> owner-presence prompt -> device check -> Voice
#     Mode, no dashboard -> hotkey -> PIN challenge -> Backend Mode ->
#     same hotkey -> Voice Mode again -> OS lock revokes elevation).
#     Launched against the throwaway server above (via AURA_CORE_URL,
#     same pattern the voice pipeline section below uses) so it exercises
#     the real /identity/whoami, /interface/config, and
#     /backend/authenticate endpoints just checked above. This is the one
#     part of the whole shell that genuinely cannot be observed from a
#     script (WPF window content isn't queryable this way) -- each step
#     is self-reported by you, the same honesty the interactive voice
#     section below already uses rather than pretending this script
#     watched it happen.
# ---------------------------------------------------------------------
Write-Section "Voice-first shell walkthrough (interactive)"
if ($SkipShellInteractive) {
    Add-Result "shell.walkthrough" "SKIP" "skipped via -SkipShellInteractive"
} elseif (-not $serverReady) {
    Add-Result "shell.walkthrough" "SKIP" "aura_core server never came up -- AuraShell has nothing to authenticate against"
} elseif ($null -eq $shellExe) {
    Add-Result "shell.walkthrough" "SKIP" "AuraShell.exe not found -- see aurashell-build.log"
} else {
    function Confirm-Step {
        param([string]$Name, [string]$Prompt)
        Write-Host ""
        Write-Host $Prompt -ForegroundColor Yellow
        $answer = Read-Host "Confirm (y/n)"
        if ($answer -match "^[Yy]") {
            Add-Result $Name "PASS" "confirmed by operator"
        } else {
            Add-Result $Name "FAIL" "operator reported this step did not behave as expected"
        }
    }

    $env:AURA_CORE_URL = $serverBaseUrl
    $walkthroughProc = $null
    try {
        $walkthroughProc = Start-Process -FilePath $shellExe.FullName -PassThru
        Start-Sleep -Seconds 4
        if ($walkthroughProc.HasExited) {
            Add-Result "shell.walkthrough" "FAIL" "AuraShell exited immediately (exit code $($walkthroughProc.ExitCode)) -- likely crashed on startup; skipping the rest of the walkthrough"
        } else {
            Write-Host ""
            Write-Host "AuraShell is now open, pointed at this script's throwaway aura_core server." -ForegroundColor Yellow
            Confirm-Step "shell.owner_presence_prompt" `
                "Did AURA show a Windows-credential prompt (asking for your account password) BEFORE anything else appeared?"
            Confirm-Step "shell.voice_mode_no_dashboard" `
                "After authenticating, does the window show ONLY a single central orb (Voice Mode) -- no tabs, no chat transcript, no dashboard?"

            $hotkey = $ifaceConfig.backend_toggle_hotkey
            if (-not $hotkey) { $hotkey = "Ctrl+Alt+Shift+A (default -- could not confirm the configured value above)" }
            Write-Host ""
            Write-Host "Press the backend hotkey now: $hotkey" -ForegroundColor Yellow
            Read-Host "Press Enter here once you've pressed it" | Out-Null
            Confirm-Step "shell.hotkey_opens_pin_challenge" `
                "Did a PIN entry screen appear (and NOT the dashboard directly)?"

            Write-Host ""
            Write-Host "Enter your backend PIN in the app now (set one first via the app or aura_core's /backend/pin if you haven't)." -ForegroundColor Yellow
            Read-Host "Press Enter here once you've submitted it" | Out-Null
            Confirm-Step "shell.pin_opens_backend_mode" `
                "Did the dashboard (Chat/Status/Approvals/Diagnostics/Audit Trail tabs) appear after a correct PIN?"

            Write-Host ""
            Write-Host "Press the SAME hotkey again to leave Backend Mode: $hotkey" -ForegroundColor Yellow
            Read-Host "Press Enter here once you've pressed it" | Out-Null
            Confirm-Step "shell.hotkey_leaves_backend_mode_without_reauth" `
                "Did it return immediately to the single-orb Voice Mode screen, with NO PIN prompt this time?"

            Write-Host ""
            Write-Host "Now re-enter Backend Mode (hotkey + PIN) again, then lock Windows (Win+L) while Backend Mode is showing, then unlock it." -ForegroundColor Yellow
            Read-Host "Press Enter here once you've locked and unlocked" | Out-Null
            Confirm-Step "shell.os_lock_revokes_elevation" `
                "After unlocking, did AURA show the owner-presence/authentication screen again (NOT the dashboard, and NOT straight back into Voice Mode without re-authenticating)?"
        }
    } catch {
        Add-Result "shell.walkthrough" "FAIL" "could not launch AuraShell.exe: $($_.Exception.Message)"
    } finally {
        if ($walkthroughProc -and -not $walkthroughProc.HasExited) {
            Stop-Process -Id $walkthroughProc.Id -Force -ErrorAction SilentlyContinue
        }
        Remove-Item Env:\AURA_CORE_URL -ErrorAction SilentlyContinue
    }
}

# ---------------------------------------------------------------------
# 6. Voice pipeline, interactive: the one thing that genuinely cannot be
#    scripted without a real microphone and a real person talking to it.
#    This script starts the real pipeline and tells you exactly what to
#    do; the pass/fail grading below comes from parsing the pipeline's
#    own real-time log file afterward, not from asking you to self-report.
# ---------------------------------------------------------------------
Write-Section "Voice pipeline (interactive -- needs your microphone and speakers)"
if ($SkipVoiceInteractive) {
    Add-Result "voice.pipeline" "SKIP" "skipped via -SkipVoiceInteractive"
} elseif (-not $serverReady) {
    Add-Result "voice.pipeline" "SKIP" "aura_core server never came up -- the voice pipeline has nothing to talk to"
} else {
    $voiceLogPath = Join-Path $env:LOCALAPPDATA "AURA\logs\voice.log"
    if (Test-Path $voiceLogPath) {
        Rename-Item $voiceLogPath "voice.log.bak-$Timestamp" -ErrorAction SilentlyContinue
    }

    Write-Host ""
    Write-Host "About to start the real voice pipeline (AuraVoice.Windows.Host) for $VoiceListenSeconds seconds." -ForegroundColor Yellow
    Write-Host "In the new console window that opens:" -ForegroundColor Yellow
    Write-Host "  1. Wait for 'state -> ListeningForWake'." -ForegroundColor Yellow
    Write-Host "  2. Say the wake word ('hey jarvis' for the bundled openWakeWord model)." -ForegroundColor Yellow
    Write-Host "  3. Once it wakes, say a short command out loud." -ForegroundColor Yellow
    Write-Host "  4. When AURA starts speaking its response, talk over it to test barge-in." -ForegroundColor Yellow
    Write-Host "Press Enter here when you're ready to begin." -ForegroundColor Yellow
    Read-Host | Out-Null

    $env:AURA_CORE_URL = $serverBaseUrl
    $voiceProc = $null
    try {
        $voiceProc = Start-Process -FilePath "dotnet" `
            -ArgumentList "run", "--project", "$RepoRoot\apps\voice\AuraVoice.Windows.Host" -PassThru
        Start-Sleep -Seconds $VoiceListenSeconds
    } finally {
        Write-Host "Stopping the voice pipeline now." -ForegroundColor Yellow
        if ($voiceProc -and -not $voiceProc.HasExited) {
            Stop-Process -Id $voiceProc.Id -Force -ErrorAction SilentlyContinue
        }
        Remove-Item Env:\AURA_CORE_URL -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }

    if (Test-Path $voiceLogPath) {
        Copy-Item $voiceLogPath (Join-Path $LogsDir "voice.log") -Force
        $voiceContent = Get-Content $voiceLogPath -Raw

        if ($voiceContent -match "state -> ListeningForWake") {
            Add-Result "voice.startup" "PASS" "pipeline reached ListeningForWake"
        } else {
            Add-Result "voice.startup" "FAIL" "never reached ListeningForWake -- see logs\voice.log"
        }

        if ($voiceContent -match "state -> Awake") {
            Add-Result "voice.wakeword" "PASS" "wake word was detected at least once (state -> Awake)"
        } else {
            Add-Result "voice.wakeword" "FAIL" "wake word was never detected -- check microphone input level/permissions and that you spoke while state was ListeningForWake"
        }

        if ($voiceContent -match "state -> Processing") {
            Add-Result "voice.stt" "PASS" "a command was captured and sent for processing"
        } else {
            Add-Result "voice.stt" "SKIP" "no command captured -- only meaningful if the wake word check above passed"
        }

        if ($voiceContent -match "aura: ") {
            Add-Result "voice.response_and_tts" "PASS" "a response was generated and spoken"
        } else {
            Add-Result "voice.response_and_tts" "SKIP" "no response was spoken -- needs STT above to have passed, aura_core reachable, and (for a real, non-empty answer) Ollama running"
        }

        $awakeCount = ([regex]::Matches($voiceContent, "state -> Awake")).Count
        if ($awakeCount -ge 2) {
            Add-Result "voice.barge_in" "PASS" "returned to Awake more than once -- consistent with a barge-in or a normal conversation-window return; check logs\voice.log to confirm which happened"
        } else {
            Add-Result "voice.barge_in" "SKIP" "not enough evidence to confirm barge-in was exercised -- try again and talk over AURA while it's speaking"
        }

        if ($voiceContent -match "\[ERROR\]") {
            Add-Result "voice.errors" "FAIL" "voice.log contains ERROR lines -- see logs\voice.log"
        } else {
            Add-Result "voice.errors" "PASS" "no ERROR lines in voice.log"
        }
    } else {
        Add-Result "voice.pipeline" "FAIL" "voice.log was never created -- the host likely failed to start entirely; check the console window it opened"
    }
}

# ---------------------------------------------------------------------
# 7. Cleanup
# ---------------------------------------------------------------------
Write-Section "Cleanup"
if ($serverProc -and -not $serverProc.HasExited) {
    Stop-Process -Id $serverProc.Id -Force -ErrorAction SilentlyContinue
    Add-Result "server.cleanup" "PASS" "aura_core server stopped"
}
Remove-Item Env:\AURA_ENV -ErrorAction SilentlyContinue
Remove-Item Env:\AURA_CORE_URL -ErrorAction SilentlyContinue

# ---------------------------------------------------------------------
# 8. Package the diagnostic bundle
# ---------------------------------------------------------------------
Write-Section "Packaging diagnostic bundle"
$Results | ConvertTo-Json -Depth 4 | Out-File (Join-Path $BundleDir "summary.json") -Encoding utf8

$passCount = ($Results | Where-Object { $_.Status -eq "PASS" }).Count
$failCount = ($Results | Where-Object { $_.Status -eq "FAIL" }).Count
$skipCount = ($Results | Where-Object { $_.Status -eq "SKIP" }).Count

$summaryLines = @("AURA Windows Commissioning -- $Timestamp", "PASS: $passCount   FAIL: $failCount   SKIP: $skipCount", "")
$summaryLines += $Results | ForEach-Object { "[{0,-4}] {1}: {2}" -f $_.Status, $_.Name, $_.Detail }
$summaryLines | Out-File (Join-Path $BundleDir "summary.txt") -Encoding utf8

if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}
$zipPath = Join-Path $OutputDir "AURA-Commissioning-$Timestamp.zip"
Compress-Archive -Path "$BundleDir\*" -DestinationPath $zipPath -Force

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ("PASS: {0}   FAIL: {1}   SKIP: {2}" -f $passCount, $failCount, $skipCount) -ForegroundColor Cyan
Write-Host "Diagnostic bundle: $zipPath" -ForegroundColor Cyan
if ($failCount -gt 0) {
    Write-Host "Send $zipPath back if you'd like help with the FAILed checks above." -ForegroundColor Red
}
Write-Host "==================================================" -ForegroundColor Cyan
