#Requires -Version 5.1
<#
.SYNOPSIS
    AURA Windows installer: preflight, staged install, self-test, and
    transactional commit with rollback on failure.

.DESCRIPTION
    Real installer logic, written carefully -- but this script has never
    been run on Windows (this codebase was authored in a cloud Linux
    container with no Windows available). Treat it as a careful first
    draft, not verified software, until you run it. See
    WINDOWS-COMMISSIONING.ps1 for the hardware-dependent validation this
    installer cannot self-certify.

    Staging strategy: everything is built/installed into a fresh
    "<InstallDir>.staging" directory first. Only after preflight AND the
    Python self-test suite pass is the staging directory swapped in for
    the real install directory (a rename, effectively atomic on the same
    volume). If anything fails before that swap, nothing about a
    pre-existing install has been touched. This is the "one-time
    installer with preflight, staging, self-test, and transactional
    commit" pattern from the product brief, implemented as literally as
    a PowerShell script reasonably allows.

.PARAMETER InstallDir
    Where AURA should live. Defaults to $env:LOCALAPPDATA\AURA.
#>
[CmdletBinding()]
param(
    [string]$InstallDir = "$env:LOCALAPPDATA\AURA"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$StagingDir = "$InstallDir.staging"
$BackupDir = "$InstallDir.backup"

function Write-Step($message) {
    Write-Host "==> $message" -ForegroundColor Cyan
}

function Write-Failure($message) {
    Write-Host "FAILED: $message" -ForegroundColor Red
}

function Invoke-Rollback {
    Write-Step "Rolling back -- removing incomplete staging directory"
    if (Test-Path $StagingDir) {
        Remove-Item -Recurse -Force $StagingDir -ErrorAction SilentlyContinue
    }
    if (Test-Path $BackupDir) {
        Write-Step "Restoring previous install from backup"
        if (Test-Path $InstallDir) {
            Remove-Item -Recurse -Force $InstallDir -ErrorAction SilentlyContinue
        }
        Rename-Item $BackupDir $InstallDir
    }
}

try {
    Write-Step "Preflight checks"
    $preflight = & python "$RepoRoot\install\preflight.py"
    $preflight | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -ne 0) {
        throw "Preflight checks failed -- see FAIL lines above."
    }

    Write-Step "Staging into $StagingDir"
    if (Test-Path $StagingDir) {
        Remove-Item -Recurse -Force $StagingDir
    }
    New-Item -ItemType Directory -Path $StagingDir | Out-Null
    Copy-Item -Recurse "$RepoRoot\core" "$StagingDir\core"
    Copy-Item -Recurse "$RepoRoot\apps" "$StagingDir\apps"
    Copy-Item -Recurse "$RepoRoot\install" "$StagingDir\install"

    Write-Step "Creating Python virtual environment"
    python -m venv "$StagingDir\core\.venv"
    $venvPython = "$StagingDir\core\.venv\Scripts\python.exe"

    Write-Step "Installing aura-core (editable) with test extras"
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -e "$StagingDir\core[test,browser,email,voice,desktop_control]"
    if ($LASTEXITCODE -ne 0) {
        throw "pip install failed"
    }

    Write-Step "Running the Python self-test suite (this is the install-time proof it actually works, not just that files copied)"
    Push-Location "$StagingDir\core"
    try {
        & $venvPython -m pytest -q
        if ($LASTEXITCODE -ne 0) {
            throw "Self-test suite failed -- see pytest output above."
        }
    } finally {
        Pop-Location
    }

    Write-Step "Building the Windows shell and voice projects"
    dotnet build "$StagingDir\apps\windows\AuraShell.sln" --configuration Release
    if ($LASTEXITCODE -ne 0) {
        throw "AuraShell.sln build failed"
    }
    dotnet build "$StagingDir\apps\voice\AuraVoice.sln" --configuration Release
    if ($LASTEXITCODE -ne 0) {
        throw "AuraVoice.sln build failed"
    }

    Write-Step "Committing: swapping staging into place"
    if (Test-Path $BackupDir) {
        Remove-Item -Recurse -Force $BackupDir
    }
    if (Test-Path $InstallDir) {
        Rename-Item $InstallDir $BackupDir
    }
    Rename-Item $StagingDir $InstallDir

    if (Test-Path $BackupDir) {
        Write-Step "Preserving prior install's persistent data (memory/governance DB, .models) into the new install"
        $oldDb = "$BackupDir\core\aura_core.db"
        if (Test-Path $oldDb) {
            Copy-Item $oldDb "$InstallDir\core\aura_core.db" -Force
        }
        $oldModels = "$BackupDir\core\.models"
        if (Test-Path $oldModels) {
            Copy-Item -Recurse $oldModels "$InstallDir\core\.models" -Force
        }
    }

    Write-Host ""
    Write-Host "AURA installed to $InstallDir" -ForegroundColor Green
    Write-Host "Next: see $InstallDir\core\RUNBOOK.md to start Ollama and run 'aura status'."
}
catch {
    Write-Failure $_.Exception.Message
    Invoke-Rollback
    exit 1
}
