# Deploying to IONOS: app.arfaat.com/worldofislam

This is the IONOS-specific companion to `docs/deployment/base-path.md`
(read that first for *why* each variable exists). No application code needs
to change for this deployment - the `/worldofislam` base path is already
built in. What's missing in a fresh deployment is: a server that can run
Node.js and Python long-running processes, a database, and the production
values for the environment variables `base-path.md` documents.

## 0. Which IONOS product do you have?

This app is a Next.js server + a FastAPI server + PostgreSQL + Redis - it
cannot run on a shared/"Webspace" hosting plan (those only serve static
files or PHP over FTP). Log into the IONOS control panel and check the
product name for app.arfaat.com's hosting:

- **VPS, Cloud Server, or Dedicated Server** - correct product. You get
  root SSH access to a Linux box; everything below applies directly.
- **Web Hosting / Webspace / "Deluxe"/"Business" hosting** - wrong product
  for this app. You'd need to add or switch to a VPS/Cloud Server plan
  first; nothing below will work on a pure shared-hosting plan.

Everything from here on assumes a VPS/Cloud Server running Ubuntu (22.04 or
24.04) with root/sudo SSH access, which is what IONOS's VPS and Cloud
Server products give you.

## 1. Point the domain at the server

In the IONOS DNS panel for `arfaat.com`, add/edit an **A record** for the
`app` subdomain pointing at your VPS's public IPv4 address (and an
**AAAA record** too if the VPS has IPv6). DNS propagation can take up to a
few hours.

## 2. Install the runtime

```bash
sudo apt update && sudo apt install -y curl git nginx postgresql redis-server certbot python3-certbot-nginx
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
corepack enable   # gives you pnpm 10.15.1 per package.json's packageManager field
curl -LsSf https://astral.sh/uv/install.sh | sh   # installs uv for the Python side
```

Create a dedicated, unprivileged user to run the app (referenced by the
systemd units in this directory):

```bash
sudo useradd -r -m -d /opt/world-of-islam -s /usr/sbin/nologin woi
```

## 3. Database

You said this isn't decided yet - for a single VPS, running Postgres and
Redis on the same box is the simplest option and needs no extra IONOS
product:

```bash
sudo -u postgres createuser world_of_islam --pwprompt
sudo -u postgres createdb world_of_islam --owner=world_of_islam
```

If you'd rather use a managed database (IONOS's managed Postgres, or
another provider) instead, skip this and just point `WOI_DATABASE_URL` at
it in step 5 - nothing else here changes.

The API also requires an S3-compatible object store (`WOI_S3_*` below) -
either run MinIO on the VPS (`infrastructure/scripts/init-minio.sh` in this
repo sets up a local one for dev and is a reasonable starting point for
production too) or point it at IONOS Object Storage / any S3-compatible
bucket you already have.

## 4. Get the code and build it

```bash
sudo -u woi git clone <your-repo-url> /opt/world-of-islam
cd /opt/world-of-islam
sudo -u woi corepack enable
sudo -u woi pnpm install --frozen-lockfile
```

## 5. Configure and build the API

```bash
cd /opt/world-of-islam/apps/api
sudo -u woi uv sync
sudo -u woi cp ../../.env.example .env   # then edit .env, see values below
sudo -u woi uv run alembic -c alembic.ini upgrade head
```

Production values for `apps/api/.env` (see `docs/deployment/base-path.md`
§2 for why each of these matters):

```
WOI_ENVIRONMENT=production
WOI_DATABASE_URL=postgresql+asyncpg://world_of_islam:<real-password>@localhost:5432/world_of_islam
WOI_REDIS_URL=redis://localhost:6379/0
WOI_CELERY_BROKER_URL=redis://localhost:6379/1
WOI_CELERY_RESULT_BACKEND=redis://localhost:6379/2
WOI_S3_ENDPOINT=<your object storage endpoint>
WOI_S3_ACCESS_KEY=<real value>
WOI_S3_SECRET_KEY=<real value>
WOI_ALLOWED_ORIGINS=https://app.arfaat.com
WOI_SECRET_KEY=<generate with: openssl rand -hex 32>
WOI_COOKIE_SECURE=true
WOI_COOKIE_PATH=/worldofislam
WOI_ROOT_PATH=
WOI_FORWARDED_ALLOW_IPS=127.0.0.1
```

Leave `WOI_ROOT_PATH` empty - the nginx config in this directory strips
`/worldofislam` before forwarding to the API (option 4a in `base-path.md`),
so the API itself never needs to know the prefix exists.

## 6. Build the web app

`WOI_BASE_PATH` and `NEXT_PUBLIC_WOI_API_ORIGIN` are compiled into the
client bundle at **build time** - set them as real shell/CI environment
variables for the build command itself, not just in a `.env` file the app
reads at runtime:

```bash
cd /opt/world-of-islam
sudo -u woi env \
  WOI_BASE_PATH=/worldofislam \
  NEXT_PUBLIC_WOI_API_ORIGIN=https://app.arfaat.com/worldofislam \
  pnpm --filter @world-of-islam/web build
```

Because `outputFileTracingRoot` is set to the monorepo root, the standalone
server must be run from a directory that has both `apps/web/server.js` and
the monorepo's `node_modules` alongside it:

```bash
sudo -u woi mkdir -p /opt/world-of-islam/web-standalone
sudo -u woi cp -r apps/web/.next/standalone/. /opt/world-of-islam/web-standalone/
sudo -u woi mkdir -p /opt/world-of-islam/web-standalone/apps/web/.next
sudo -u woi cp -r apps/web/.next/static /opt/world-of-islam/web-standalone/apps/web/.next/static
sudo -u woi cp -r apps/web/public /opt/world-of-islam/web-standalone/apps/web/public
```

Re-run this whole step (build + copy) any time you deploy new code, or
change `WOI_BASE_PATH`/`NEXT_PUBLIC_WOI_API_ORIGIN` - a stale
`web-standalone` directory serves stale JS.

## 7. Run both as services

```bash
sudo cp infrastructure/ionos/woi-api.service infrastructure/ionos/woi-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now woi-api woi-web
sudo systemctl status woi-api woi-web   # both should be "active (running)"
curl -s http://127.0.0.1:8000/health/live
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3000
```

## 8. Certificate and reverse proxy

```bash
sudo certbot certonly --nginx -d app.arfaat.com   # or --webroot if nginx isn't running yet
sudo cp infrastructure/ionos/nginx-app.arfaat.com.conf /etc/nginx/sites-available/app.arfaat.com
sudo ln -s /etc/nginx/sites-available/app.arfaat.com /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

## 9. Verify

- `https://app.arfaat.com/worldofislam/api/health/ready` - should report the
  database, Redis, and object storage as connected.
- `https://app.arfaat.com/worldofislam` - should redirect to `/en` and load
  the app over HTTPS.
- Register a real account through the UI and confirm login works (this
  exercises the cookie `Path`/`Secure` settings end to end).

## What redeploying looks like later

1. `git pull` in `/opt/world-of-islam`.
2. Re-run step 5's `alembic upgrade head` if there are new migrations.
3. Re-run step 6 (build + copy to `web-standalone`) - always, even for
   API-only changes, since a stale build silently keeps serving old JS.
4. `sudo systemctl restart woi-api woi-web`.
