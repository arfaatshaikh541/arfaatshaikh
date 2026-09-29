# Running with plain Python (no Docker)

Everything runs as normal Python processes. PostgreSQL is still required (the queue locking and
duplicate-submission protection depend on it), but you don't have to install it: `autopilot setup`
uses a **built-in PostgreSQL** (the `pgserver` pip package) that lives in your data folder.

Requirements: **Python 3.11 or 3.12** (the built-in database has no builds for 3.13+ yet), git, and
about 1 GB of disk. Works on Linux, macOS and Windows (tested on Linux).

## Install and start

```bash
git clone -b claude/job-autopilot-system-1nyk4w https://github.com/arfaatshaikh/arfaatshaikh.git
cd arfaatshaikh/job-autopilot
python3.12 -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -e ".[embedded]"

autopilot setup                     # writes .env, creates the master key, downloads Chromium, prepares the DB
autopilot create-admin --email you@example.com
autopilot run                       # web + scheduler + worker; open http://127.0.0.1:8000
```

Stop with **Ctrl+C**. Workers finish their current step, then everything stops, including the database.
Start again later with `autopilot run` from the same folder (your data is kept in `autopilot-data/`).

* `setup` writes its settings to `.env` in the current folder, and every `autopilot` command reads it,
  so always run commands from that folder.
* **Back up `autopilot-data/master.key`.** Without it your stored passwords and CV can't be decrypted.
  Backing up the whole `autopilot-data/` folder while it is stopped backs up everything.
* On Linux, if Chromium fails to start, install its system libraries once:
  `sudo venv/bin/python -m playwright install-deps chromium`
* Use your own PostgreSQL instead: `autopilot setup --database-url postgresql+psycopg://user:pass@localhost/autopilot`
* More workers: `autopilot run --workers 2`

## What `autopilot run` does

It starts the dashboard, the scheduler and one or more workers as child processes and watches them.
A process that crashes is restarted automatically (backoff 1 s → 60 s), which is the same role the
Docker restart policy plays. On Ctrl+C / SIGTERM it stops them gracefully.

## 24/7 without Docker

On your own computer it only runs while the computer is on and awake. For 24/7 operation, run the
same steps on a Linux server and let systemd keep `autopilot run` alive across crashes and reboots:
see `deploy/systemd/job-autopilot.service` (instructions at the top of the file). Put HTTPS in front
of it (e.g. Caddy: `reverse_proxy 127.0.0.1:8000`), then set `JOBAP_SECURE_COOKIES=true` and
`JOBAP_PUBLIC_BASE_URL=https://your-domain` in `.env`.

## Verified in the build environment

In a fresh virtualenv, as a normal (non-root) user: `pip install -e ".[embedded]"`, `autopilot setup`,
`create-admin`, `run` → dashboard login, health **ONLINE** (scheduler RUNNING, worker 1/1 ALIVE,
vault healthy); a SIGKILLed worker was restarted by the supervisor within 1 s; Ctrl+C stopped every
process including the built-in PostgreSQL in 4 s. (The Chromium download step could not be tested
there because that environment blocks Playwright's download server.)
