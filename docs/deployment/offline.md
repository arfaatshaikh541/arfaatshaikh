# Offline support

## What's real

`apps/web/public/sw.js` is a minimal, hand-written service worker (no
`next-pwa` or similar dependency added) registered by
`apps/web/src/components/service-worker-registration.tsx` at the
deployment's actual base path (`NEXT_PUBLIC_WOI_BASE_PATH`, mirrored from
`WOI_BASE_PATH` in `next.config.ts`).

It caches exactly two things:
- **Pages you have actually visited**, network-first (so a signed-in session
  and fresh content are always preferred over anything cached), falling
  back to the cached copy of that exact page only when the network is
  unreachable.
- **`_next/static/**` build assets**, cache-first (safe because every such
  URL already contains a content hash and never changes meaning).

It explicitly never intercepts anything under `/api/` (session-sensitive,
must always be live) or cross-origin requests.

`apps/web/src/app/manifest.ts` provides installable-app metadata (name,
theme colors, one SVG icon derived from the existing brand mark). `start_url`
and the icon path are both relative, so they resolve correctly under any
base path without hardcoding one.

## What was actually verified (Playwright, real browser, not simulated)

1. Built the production app with `WOI_BASE_PATH=/worldofislam`, served it
   with the standalone server, confirmed `GET /worldofislam/manifest.webmanifest`,
   `GET /worldofislam/sw.js`, and `GET /worldofislam/icon.svg` all return `200`.
2. Loaded `/worldofislam/en/w`, waited for the service worker to reach
   `activated` state at scope `http://.../worldofislam/`, then visited a
   second page.
3. Set the browser context fully offline (`context.setOffline(true)`) and
   reloaded the **first** page: it returned HTTP `200` from the cache with
   the real, correct page content (not a browser offline error page).

See `WORLD_OF_ISLAM_FINAL_REPORT.md` for the exact command/output log.

## What this does NOT do (by design, not oversight)

- **No Islamic knowledge content (Qur'an/Hadith/Tafsir text) is cached or
  bundled for offline use.** This dev environment's database has no
  imported corpus to cache in the first place, and caching real source text
  offline deserves its own licensing review before being added - "offline
  Qur'an" and "Offline Islam" remain `planned` in the feature registry, not
  `available`.
- No background sync, no IndexedDB data layer, no conflict resolution for
  offline-created content - there is no offline-capable read/write feature
  in this app yet, only a read-only shell cache.
- Cross-browser/cross-platform install behavior (Safari, Firefox, various
  Android/iOS home-screen install flows) is **NOT VERIFIED** - only Chromium
  via Playwright was exercised.
