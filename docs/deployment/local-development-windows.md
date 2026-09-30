# Running World of Islam locally on Windows (no prior dev setup assumed)

This is a beginner-friendly companion to `docs/deployment/local-development.md`
(which assumes you already have a dev environment). Follow these phases in
order; each one builds on the last.

## Phase 1 - Install the tools

Install each of these with their default settings unless noted:

1. **Git for Windows** - https://git-scm.com/download/win
   Gives you "Git Bash", a terminal that behaves like the Linux/Mac one this
   project's own docs assume. Use Git Bash for every command below instead
   of Command Prompt.
2. **Node.js LTS** (20.x or newer) - https://nodejs.org/en/download
   Pick the Windows installer, "LTS" version.
3. **Python 3.12** - https://www.python.org/downloads/windows/
   On the first installer screen, tick **"Add python.exe to PATH"** before
   clicking Install - easy to miss, and everything after this step depends
   on it.
4. **Docker Desktop for Windows** - https://www.docker.com/products/docker-desktop/
   This is only used to run the database (Postgres) and Redis - not the app
   itself. The installer may ask to enable WSL2 and restart your PC; let it.
   After install, open Docker Desktop once and make sure it says "Engine
   running" (bottom left) before continuing.

Restart your PC after these installs if anything asked you to.

## Phase 2 - Get the code

1. Open the GitHub repository page in your browser.
2. Click the green **"Code"** button -> **"Download ZIP"**.
3. Switch to the `claude/world-of-islam-webapp-9rfzue` branch first (the
   branch dropdown near the top-left of the file list) - the ZIP button
   downloads whichever branch is currently selected.
4. Extract the ZIP somewhere easy to find, e.g. `Documents\world-of-islam`.

## Phase 3 - Start the database

Open **Git Bash** (Start menu -> search "Git Bash") and run:

```bash
docker run -d --name woi-postgres -e POSTGRES_USER=world_of_islam \
  -e POSTGRES_PASSWORD=devpassword -e POSTGRES_DB=world_of_islam \
  -p 5432:5432 postgres:16

docker run -d --name woi-redis -p 6379:6379 redis:7
```

Check both are running:

```bash
docker ps
```

You should see `woi-postgres` and `woi-redis` listed as `Up`.

## Phase 4 - Configure and start the API

In Git Bash, navigate to where you extracted the code (adjust the path):

```bash
cd ~/Documents/world-of-islam-worldofislam-webapp-9rfzue
```

Install `uv` (the Python tool this project uses):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Create the API's config file:

```bash
cp .env.example apps/api/.env
```

Open `apps/api/.env` in Notepad (`notepad apps/api/.env`) and make sure
these lines match (they should already be close to this from the template -
just confirm, since Phase 3's containers used these exact credentials):

```
WOI_DATABASE_URL=postgresql+asyncpg://world_of_islam:devpassword@localhost:5432/world_of_islam
WOI_REDIS_URL=redis://localhost:6379/0
WOI_CELERY_BROKER_URL=redis://localhost:6379/1
WOI_CELERY_RESULT_BACKEND=redis://localhost:6379/2
WOI_SECRET_KEY=any-random-string-at-least-32-characters-long
WOI_ALLOWED_ORIGINS=http://localhost:3000
```

For local testing you can leave the `WOI_S3_*` lines as their placeholder
values - object storage features will just report unavailable, everything
else works fine.

Install dependencies, run migrations, and start the API:

```bash
cd apps/api
uv sync
uv run alembic -c alembic.ini upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

Leave this window running. Open `http://localhost:8000/health/live` in your
browser - it should show a small JSON status message.

## Phase 5 - Configure and start the web app

Open a **second** Git Bash window (leave the first one running the API).
Navigate to the same folder, then:

```bash
corepack enable
pnpm install
pnpm --filter @world-of-islam/web dev
```

Leave this running too.

## Phase 6 - Open it

Go to `http://localhost:3000` in your browser - it should redirect to
`http://localhost:3000/en`. Register an account through the UI and click
around; this is a full local copy, nothing here touches the live IONOS
server or app.arfaat.com.

## Stopping / restarting later

- Stop the two `pnpm`/`uvicorn` windows with `Ctrl+C`.
- The database keeps its data between restarts. To start it again later:
  `docker start woi-postgres woi-redis`.
- To wipe the local database and start over:
  `docker rm -f woi-postgres woi-redis` and repeat Phase 3.

## Phase 7 - Load the Qur'an and Hadith text (so Search and the Assistant have content)

With the database running and migrated (Phase 4), open a Git Bash window in
`apps/api` and run:

```bash
uv run python scripts/import_real_evidence.py
```

It downloads the two source packages from PyPI, checks their checksums, and
loads about 6,200 ayat and 7,400 hadith through the platform's normal review
and approval steps. It takes a few minutes and is safe to re-run (it skips
sources that are already loaded).

### Then publish the readers

The Qur'an and Hadith reader pages use their own tables. After the step above, run:

```bash
uv run python scripts/import_quran_reader.py
uv run python scripts/import_hadith_reader.py
```

This publishes 114 surahs / 6,236 ayahs, Sahih Muslim (57 books, 7,459
narrations) and Sahih al-Bukhari (97 books, 7,277 narrations), each with its English translation. Re-run `uv run alembic -c alembic.ini upgrade head`
first if you set up the database before 2026-09-29 (a migration adds missing timestamp defaults).

Then load Tajweed and Tafsir (needs internet; Tafsir takes a few minutes):

```bash
uv run python scripts/import_tajweed.py
uv run python scripts/import_tafsir.py
```

Every source, its licence and what was verified is listed in `docs/data-sources.md`.

## Troubleshooting

- **Port 8000 already used** (`WinError 10013`): start the API on another
  port, e.g. `--port 8010`, and create `apps/web/.env.local` containing
  `NEXT_PUBLIC_WOI_API_ORIGIN=http://localhost:8010`. Delete `apps/web/.next`
  and restart the web app afterwards.
- **"Could not reach the server" on the register or login page**: the address
  in your browser must be listed in `WOI_ALLOWED_ORIGINS` in `apps/api/.env`
  (for example `http://localhost:3000,http://localhost:3001`).
