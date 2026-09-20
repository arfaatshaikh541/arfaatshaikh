# AURA Installer

| File | Verified here? |
|---|---|
| `preflight.py` | **Yes.** Pure-stdlib Python, runs on any OS. Actually executed in this session (see `core/tests/test_preflight.py`, 3 tests, all passing) — checks Python version, pip, .NET SDK presence, Ollama reachability, disk space, write permission, espeak-ng-data, and voice model files, real inspection each time, not a canned response. |
| `Install-AURA.ps1` | **No — cannot be, in this environment.** There is no `pwsh`/PowerShell available in this cloud Linux container, and no reachable package source for it was found (Microsoft's own package repos are not on this sandbox's network allowlist; confirmed by trying). Written carefully, following standard staged-install/rollback conventions, but never executed. Run it yourself and tell me what breaks. |

## What `Install-AURA.ps1` actually does (by design)

1. Runs `preflight.py` and aborts if anything is FAIL-level.
2. Copies the repo into a `.staging` directory — the real install directory is never touched yet.
3. Creates a fresh Python venv and installs `aura-core` with all optional extras inside staging.
4. **Runs the actual Python test suite inside the staged install** as the install-time proof it works, not just that files copied — this is the literal implementation of "run a real self-test before committing," not a checkbox.
5. Builds both `.sln`s (`AuraShell`, `AuraVoice`) in Release configuration.
6. Only after all of the above succeed: renames the old install directory to `.backup`, renames `.staging` into place, and copies forward the previous install's database and downloaded voice models.
7. On any failure at any step, rolls back: deletes the incomplete staging directory and restores `.backup` if one exists. A failed install leaves a working prior install (if any) exactly as it was.

## Running it

```powershell
# From the repo root on your Windows machine:
.\install\Install-AURA.ps1
```

Or just the preflight check on its own, anytime:

```powershell
python install\preflight.py
```
