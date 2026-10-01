# Production deployment (Docker Compose): VPS or AWS EC2

Target: `https://app.arfaat.com/worldofislam`.

```
Internet ──443/80──▶ nginx ──▶ web (Next.js, basePath /worldofislam)
                         └───▶ api (FastAPI)  ──▶ postgres, redis, minio, ollama   (private network)
                                      worker (Celery) ─▶ redis, postgres
                                      backup (pg_dump nightly)
```

Only nginx publishes ports. PostgreSQL, Redis, MinIO, Ollama, Celery and the API/web containers have no
published port and sit on Docker networks the internet cannot reach (`backend` is `internal: true`).

## 1. Server prerequisites

| | VPS (IONOS, any Ubuntu 22.04/24.04) | AWS EC2 |
|---|---|---|
| Size | 4 GB RAM / 2 vCPU minimum; 8 GB+ if you run Ollama | `t3.large` (8 GB) minimum with Ollama; `t3.medium` without |
| Disk | 40 GB+ | 50 GB gp3 |
| Firewall | allow 22, 80, 443 only | Security group inbound: 22 (your IP only), 80, 443 from anywhere. **Nothing else.** |
| DNS | `A` record `app` → server IPv4 | Elastic IP, then `A` record `app` → that address |

Install Docker Engine + Compose plugin (Ubuntu):

```bash
sudo apt update && sudo apt install -y ca-certificates curl git certbot
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER   # log out and back in
```

Host firewall on a plain VPS (EC2 uses the security group instead):

```bash
sudo ufw allow 22/tcp && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw enable
```

Docker publishes ports by editing iptables directly, which bypasses `ufw`. That is fine here because the
compose file publishes only 80 and 443. Do not add `ports:` to any other service.

## 2. Get the code and configure

```bash
git clone <your-repo-url> world-of-islam && cd world-of-islam
git checkout claude/world-of-islam-webapp-9rfzue   # or your release branch
cp .env.production.example .env.production
nano .env.production        # replace EVERY CHANGE_ME
```

Generate each secret with `openssl rand -hex 32`. The API refuses to start in production if any value still
looks like a placeholder, if cookies are not `Secure`, if an allowed origin is not https, or if external AI is on
(`app/core/config.py`, covered by `tests/test_production_config.py`).

Required variables (all listed with comments in `.env.production.example`):

| Variable | Value |
|---|---|
| `WOI_PUBLIC_HOST` | `app.arfaat.com` |
| `WOI_BASE_PATH` | `/worldofislam` (no trailing slash) |
| `NEXT_PUBLIC_WOI_API_ORIGIN` | `https://app.arfaat.com/worldofislam` (**baked into the web build**; rebuild after changing) |
| `WOI_ENVIRONMENT` | `production` |
| `WOI_ALLOWED_ORIGINS` | `https://app.arfaat.com` |
| `WOI_SECRET_KEY` | 64 hex characters |
| `WOI_COOKIE_SECURE` / `WOI_COOKIE_PATH` | `true` / `/worldofislam` |
| `WOI_FORWARDED_ALLOW_IPS` | `172.31.200.10` (nginx's fixed address; never `*`) |
| `POSTGRES_*`, `WOI_DATABASE_URL` | same password in both |
| `REDIS_PASSWORD`, `WOI_REDIS_URL`, `WOI_CELERY_*` | same password everywhere |
| `MINIO_ROOT_USER/PASSWORD`, `WOI_S3_*` | same credentials in both groups |
| `WOI_AI_MODE=local`, `WOI_EXTERNAL_AI_ENABLED=false`, `WOI_OLLAMA_BASE_URL=http://ollama:11434`, `WOI_OLLAMA_MODEL` | local AI only |

## 3. TLS certificate (before first start)

Port 80 must be free, so do this before `docker compose up`:

```bash
sudo certbot certonly --standalone -d app.arfaat.com --agree-tos -m you@example.org
```

Renewal (certbot installs a timer; add hooks so nginx releases port 80):

```bash
sudo tee /etc/letsencrypt/renewal-hooks/pre/woi.sh >/dev/null <<'EOS'
#!/bin/sh
cd /home/ubuntu/world-of-islam && docker compose --env-file .env.production -f docker-compose.prod.yml stop nginx
EOS
sudo tee /etc/letsencrypt/renewal-hooks/post/woi.sh >/dev/null <<'EOS'
#!/bin/sh
cd /home/ubuntu/world-of-islam && docker compose --env-file .env.production -f docker-compose.prod.yml start nginx
EOS
sudo chmod +x /etc/letsencrypt/renewal-hooks/*/woi.sh      # adjust the path to where you cloned the repo
sudo certbot renew --dry-run
```

## 4. Start

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.production -f docker-compose.prod.yml ps        # everything "healthy"
curl -I https://app.arfaat.com/worldofislam/en
curl https://app.arfaat.com/worldofislam/api/health/live
```

`migrate` applies every Alembic migration before the API starts. First start also pulls images and builds the
web bundle (several minutes).

### Local AI (Ollama)

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml exec ollama ollama pull llama3.1
```

Without a pulled model the assistant still works: it returns verbatim, cited source passages and marks the AI
synthesis section "unavailable".

### Content

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm api \
  python scripts/import_real_evidence.py            # content importers (see docs/DATA_READINESS.md)
```

Importers need outbound internet; run them on the `egress`-connected container or load data on your PC and
restore a dump. Content marked LICENSE_REQUIRED / OWNER_UPLOAD_REQUIRED stays hidden until you publish it.

## 5. Backups and restore

The `backup` service writes `./backups/woi-<timestamp>.sql.gz` nightly and prunes after `BACKUP_KEEP_DAYS`.
Copy that folder off the server (S3 bucket, another host). Restore:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml stop api worker
./infrastructure/scripts/restore.sh backups/woi-20261001T020000Z.sql.gz
docker compose --env-file .env.production -f docker-compose.prod.yml start api worker
```

Also snapshot the Docker volumes `minio_data` and `ollama_data` if you rely on uploaded files.

## 6. Updating

```bash
git pull
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```

## 7. Verifying migrations on a scratch database

```bash
WOI_PG_ADMIN_URL=postgresql://user:pass@host:5432/postgres ./infrastructure/scripts/verify-migrations.sh
```

Runs upgrade → downgrade → upgrade on a throwaway database and compares schemas.

## 8. Troubleshooting

| Symptom | Cause |
|---|---|
| API exits with "Unsafe production configuration" | A value in `.env.production` is still a placeholder / not https |
| 502 from nginx right after start | web/api still starting; wait for `healthy` |
| Login works but you are logged out on the next page | `WOI_COOKIE_PATH` is not `/worldofislam`, or the site is opened over http |
| `/worldofislam/api/health/ready` returns 503 | MinIO or Redis is not healthy; `docker compose ps` |
| Many requests from one visitor are rejected with 429 | nginx rate limit (`woi.conf.template`) |
