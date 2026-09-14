# Deploying under `/worldofislam`

This document is the audit and configuration reference required to run the
application at `https://app.arfaat.com/worldofislam` instead of at a domain
root. It covers every surface named in the base-path requirement: Next.js
config, API mounting, cookies, CORS, robots/metadata, and the reverse proxy.

## 1. Two separate deployments, same path segment

- **Public overview page** — `https://arfaat.com/worldofislam` — marketing/
  project page. Not part of this repository's `apps/web`; must never expose
  the application shell, admin, or scholar/reviewer areas.
- **Application** — `https://app.arfaat.com/worldofislam` — this repo's
  `apps/web` (Next.js) plus `apps/api` (FastAPI) behind a reverse proxy.
  Authenticated, `noindex`ed (`apps/web/src/app/robots.ts` and the root
  layout's `robots` metadata), never crawled.

Everything below is about the second deployment.

## 2. Environment variables that control the base path

| Variable | Where | Purpose |
|---|---|---|
| `WOI_BASE_PATH` | web build | Next.js `basePath`/`assetPrefix`, e.g. `/worldofislam`. Empty for local dev. Baked in at **build time** (see §5). |
| `NEXT_PUBLIC_WOI_API_ORIGIN` | web build | Public origin the browser calls for the API, e.g. `https://app.arfaat.com/worldofislam`. Baked in at **build time**. |
| `WOI_COOKIE_PATH` | api runtime | Scopes the session cookie (`Set-Cookie: ...; Path=...`) so it is never sent to unrelated apps on `app.arfaat.com`. Set to `/worldofislam` in production. |
| `WOI_ROOT_PATH` | api runtime | Only needed if the proxy forwards the external prefix to the API verbatim instead of stripping it (see §4, option B). Leave empty for the recommended option A. |
| `WOI_ALLOWED_ORIGINS` | api runtime | CORS allow-list. In production this is `https://app.arfaat.com` (no path — CORS `Origin` headers never carry a path). |

## 3. Next.js configuration (`apps/web/next.config.ts`)

`basePath`/`assetPrefix` are set from `WOI_BASE_PATH` when non-empty. Once
set, Next.js automatically:

- Prefixes every `next/link`, `useRouter().push/replace`, and `next/image`
  URL with the base path — the app's own navigation
  (`apps/web/src/components/*.tsx`) uses these exclusively, so no per-link
  changes were needed.
- Strips the base path from `request.nextUrl.pathname` inside
  `apps/web/src/middleware.ts` before the matcher and handler run, and
  re-adds it when the middleware builds a redirect from
  `request.nextUrl.clone()`. The locale-redirect middleware required no
  changes.
- Prefixes generated `robots.txt`/metadata routes the same way static assets
  are prefixed.

**Not automatic:** anything that talks to the API. `apps/web/src/lib/api.ts`
builds request URLs from `NEXT_PUBLIC_WOI_API_ORIGIN` + `/api/v1` + the
caller's path, so the public API origin must itself already include
`/worldofislam` when the API is reverse-proxied under the same path segment
(see §4).

## 4. API mounting and the `/api` split

Every FastAPI route is mounted under a single `/api/v1` prefix in
`apps/api/app/main.py` (`app.include_router(router, prefix="/api/v1")`),
except `/health/live` and `/health/ready`, which stay unprefixed and
unversioned because container orchestrators and the Docker Compose
healthcheck probe them directly inside the private network, never through
the public base path.

Previously, only the auth router carried its own `/api/v1/auth` prefix while
every other router (quran, hadith, tafsir, sources, ...) was mounted bare
(`/quran`, `/hadith`, ...). That inconsistency meant a page path like
`/worldofislam/quran/2` (a **web** route) and an API path like
`/worldofislam/quran/me/bookmarks` would collide on the same segment under a
path-based reverse proxy split — there was no way to route by path prefix
alone. Standardizing all API routes under `/api/v1` removes that collision:
the proxy can route by a single, unambiguous rule (§4a).

### 4a. Recommended: proxy strips `/worldofislam`, forwards the rest verbatim

```
https://app.arfaat.com/worldofislam/api/v1/auth/login
  → nginx strips "/worldofislam"
  → forwards "/api/v1/auth/login" to the api container, unchanged
  → matches app.include_router(router, prefix="/api/v1") + auth's "/auth" prefix
```

With this option the API code needs no knowledge of `/worldofislam` at all
— leave `WOI_ROOT_PATH` empty. `NEXT_PUBLIC_WOI_API_ORIGIN` must be set to
`https://app.arfaat.com/worldofislam` (the browser's public origin), and
`apiFetch` appends `/api/v1/<path>` itself.

### 4b. Alternative: proxy forwards the full path unchanged

If your proxy cannot strip a prefix (some managed load balancers), forward
`/worldofislam/*` to the API as-is and set `WOI_ROOT_PATH=/worldofislam` so
FastAPI's OpenAPI schema and any generated absolute URLs account for the
prefix it is actually reachable at. You would then also mount the app's
router at `/worldofislam/api/v1` instead of `/api/v1` — this is more
invasive and option A is preferred.

## 5. Build-time vs runtime variables (Docker)

`NEXT_PUBLIC_*` variables and `basePath`/`assetPrefix` are compiled into the
client bundle and the route manifest at `next build` time — setting them as
container **runtime** environment variables (e.g. only in `env_file`) has no
effect once the image is built. `apps/web/Dockerfile` now declares them as
build `ARG`s:

```dockerfile
ARG NEXT_PUBLIC_WOI_API_ORIGIN=http://localhost:8000
ARG WOI_BASE_PATH=
ENV NEXT_PUBLIC_WOI_API_ORIGIN=$NEXT_PUBLIC_WOI_API_ORIGIN
ENV WOI_BASE_PATH=$WOI_BASE_PATH
RUN pnpm --filter @world-of-islam/web build
```

and `docker-compose.yml`'s `web` service passes them through from `.env` via
`build.args`. **This means changing the base path or public API origin
always requires rebuilding the web image** — a plain `docker compose up`
without `--build` will keep serving the old values.

## 6. Reverse proxy reference (nginx)

```nginx
# app.arfaat.com
server {
    listen 443 ssl http2;
    server_name app.arfaat.com;

    # ... ssl_certificate / ssl_certificate_key / HSTS, etc.

    # Exact-path health probes for external uptime monitoring. Internal
    # container healthchecks (docker-compose.yml) hit the api container
    # directly and do not go through this proxy.
    location = /worldofislam/api/health/live {
        proxy_pass http://api:8000/health/live;
    }
    location = /worldofislam/api/health/ready {
        proxy_pass http://api:8000/health/ready;
    }

    # API: strip "/worldofislam", forward "/api/v1/..." unchanged.
    location /worldofislam/api/ {
        proxy_pass http://api:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Request-ID $request_id;
    }

    # Web app: forward the full path, including "/worldofislam", unchanged -
    # Next.js's own basePath expects to see it.
    location /worldofislam/ {
        proxy_pass http://web:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location / {
        return 404;
    }
}
```

Adjust `proxy_pass` targets for your actual network (Docker Compose service
names, a Kubernetes Service DNS name, or a load balancer target group).

## 7. Cookies and same-origin behavior

Because both the web app and the API are reverse-proxied under the same
`app.arfaat.com` origin, the browser's request to the API is **same-origin**
in production — CORS and cross-site cookie rules only matter for local
development, where `apps/web` (`localhost:3000`) and `apps/api`
(`localhost:8000`) are genuinely cross-origin. The session cookie
(`apps/api/app/api/routes/auth.py`) is `HttpOnly`, `SameSite=Lax`, and
`Secure` when `WOI_COOKIE_SECURE=true`; its `Path` is `WOI_COOKIE_PATH`,
which should be `/worldofislam` in production so the cookie is never sent to
any other application that might later share `app.arfaat.com`.

## 8. What was audited and found already correct

- **Client-side navigation** (`next/link`, `useRouter`) — already
  basePath-aware by construction; no source changes needed.
- **Middleware locale redirect** — operates on `nextUrl.pathname`, which
  Next.js already presents with the base path stripped; the redirect is
  rebuilt from `nextUrl.clone()`, which re-adds it. This held for every path
  *except* the bare base-path root, which needed a real fix — see
  `docs/testing/base-path-verification.md` for what broke and what was
  changed (`apps/web/src/app/page.tsx`).
- **CSP `connect-src`** (`next.config.ts` `headers()`) — origin-based, not
  path-based, so it is unaffected by the base path.
- **No service worker, manifest, or sitemap exists in this app** — nothing
  to audit there; a fabricated one has not been added (see project ground
  rule against creating pages/artifacts that don't correspond to real
  functionality).
