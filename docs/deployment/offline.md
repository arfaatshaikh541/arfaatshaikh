# Offline support

Offline is limited to what may lawfully be stored on a device, and the Offline page (`/{locale}/offline`) states plainly
what works without a connection and what does not.

| Capability | Offline? | How |
|---|---|---|
| Qur'an Arabic text (CC BY 4.0) | Yes, after the reader downloads it | Explicit download on the Offline page; stored in IndexedDB (`src/lib/offline.ts`); the Qur'an reader falls back to it when the API is unreachable |
| Search within the downloaded Qur'an text | Yes | Diacritic-insensitive search over IndexedDB |
| Layout of public pages already visited | Yes | Service worker (`public/sw.js`), network-first with cached fallback; hashed build assets cache-first |
| Bookmarks made while offline | Queued, synced on reconnect | IndexedDB outbox, replayed in order on the `online` event; newest write per key wins; a write the server rejects (4xx) is dropped as a conflict |
| Translations, tafsir, hadith, assistant, unified search, directory | **No** (needs internet) | Their rights or size do not permit on-device copies |

## Rules the implementation follows

- Only the Arabic text is downloaded: the reading request is made **without** a translation, so no translation whose
  rights are unconfirmed is ever copied to a device.
- The service worker never intercepts `/api/`, cross-origin requests, or non-GET requests, and never caches account,
  admin or authentication pages (`PRIVATE_PATHS` in `sw.js`).
- The worker is registered at the deployment base path (`NEXT_PUBLIC_WOI_BASE_PATH`) so it works at `/` and at
  `/worldofislam`.
- Downloads are paced and retry on HTTP 429, staying inside the server's request-rate limits.

## What was verified (real browser, Playwright, through the production nginx stack)

- Service worker registered with scope `/worldofislam/`.
- Download of the Qur'an text into IndexedDB; with the browser set offline, `/en/quran/1` rendered from the device copy
  with an "Offline copy (Arabic text only)" notice; offline search returned ayahs.
- Unit tests (`src/lib/offline.test.ts`, fake-indexeddb): storage, diacritic-insensitive search, newest-write-wins queue,
  ordered replay, conflict drop, stop-on-network-failure.

## Not verified

- Behaviour on iOS Safari (storage eviction rules differ) and on very low-storage devices.
- Background sync while the tab is closed (replay happens when a tab is open and the browser reports it is online).
