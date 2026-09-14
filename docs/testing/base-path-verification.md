# Base-path verification (actually executed, not assumed)

This records a real run against the production `standalone` build — the same
artifact `apps/web/Dockerfile` ships — with `WOI_BASE_PATH=/worldofislam` and
`NEXT_PUBLIC_WOI_API_ORIGIN=https://app.arfaat.com/worldofislam`, built and
started natively (`node apps/web/server.js`), no Docker involved. `next start`
was tried first and rejected itself ("does not work with output: standalone
configuration"), so all results below are from the actual standalone server.

## What was found and fixed

The first run surfaced a real bug: requesting the bare base path with no
locale segment (`GET /worldofislam`, and `GET /worldofislam/` after its
own redirect) returned a static **404** instead of redirecting into
`/worldofislam/en` — even though the identical case with no base path
configured (`GET /`) correctly redirected via `apps/web/src/middleware.ts`.
Every other unlocalized path (`/worldofislam/dashboard`,
`/worldofislam/anything`) redirected correctly in both configurations; only
the exact base-path root was affected — Next.js appears to resolve that
one specific path from its static not-found cache before invoking custom
middleware once a non-empty `basePath` is configured. Since the bare base
path is the literal landing URL an operator would put in a browser or a DNS
record, this was a real production blocker, not a cosmetic gap.

**Fix:** added `apps/web/src/app/page.tsx` — a real root page (outside the
`[locale]` segment) that server-redirects to `/{defaultLocale}`, so the
exact root always resolves to a rendered route instead of depending on the
middleware/not-found race. Re-verified after the fix (below).

## Commands run

```bash
WOI_BASE_PATH=/worldofislam \
NEXT_PUBLIC_WOI_API_ORIGIN=https://app.arfaat.com/worldofislam \
pnpm --filter @world-of-islam/web build

cp -r apps/web/.next/static apps/web/.next/standalone/apps/web/.next/static
cp -r apps/web/public apps/web/.next/standalone/apps/web/public

cd apps/web/.next/standalone
WOI_BASE_PATH=/worldofislam \
NEXT_PUBLIC_WOI_API_ORIGIN=https://app.arfaat.com/worldofislam \
PORT=3103 node apps/web/server.js
```

## Results (after the fix)

| Check | Request | Result |
|---|---|---|
| Base path enforced | `GET /` | `404` — app is not reachable at the domain root |
| Root redirect | `GET /worldofislam` | `307` → `/worldofislam/en` |
| Full redirect chain | `GET /worldofislam` (follow) | `200` at `/worldofislam/en` |
| Deep unlocalized path | `GET /worldofislam/dashboard` | `307` → `/worldofislam/en/dashboard` |
| Nonexistent path | `GET /worldofislam/nonexistent-xyz` | `307` → locale-prefixed (then real 404 inside the locale) |
| Static assets prefixed | HTML of `/worldofislam/en` | script `src` values are `/worldofislam/_next/static/chunks/...` |
| `assetPrefix` applied | — | confirmed via the same asset URLs above |
| robots noindex | `GET /worldofislam/robots.txt` | `User-Agent: *` / `Disallow: /` |
| RTL locale | `GET /worldofislam/ar` | `<div lang="ar" dir="rtl">` present in rendered HTML |
| API origin baked into client bundle | `grep` over `.next/standalone/.../static/chunks/**` | `https://app.arfaat.com/worldofislam` present in multiple page chunks (e.g. hadith reader, tafsir reader, forgot-password) |
| CSP header still correct | any response | `connect-src 'self' http://api:8000 https://app.arfaat.com/worldofislam` |

## What this does not cover

- No live reverse proxy (nginx/Cloudflare/etc.) was stood up — the proxy
  config in `docs/deployment/base-path.md` §6 is a reference configuration,
  not something exercised end-to-end in this environment. The API-side split
  (`/worldofislam/api/...` → strip prefix → FastAPI) was verified by
  starting the FastAPI app itself at `/api/v1/...` directly (see
  `docs/FINAL_AUDIT.md`), not through an actual nginx instance, since no
  reverse proxy or public DNS exists in this sandbox.
- TLS/HTTPS was not exercised (plain HTTP loopback only).
- Auth cookie behavior *specifically under a reverse-proxied same-origin
  setup* (§7 of the base-path doc) was verified at the API layer directly
  (cookie `Path`, `HttpOnly`, `SameSite`, CSRF enforcement — see
  `docs/FINAL_AUDIT.md`), not through the proxy, for the same reason.
