// Minimal app-shell service worker.
//
// What this caches: the pages you have actually visited, and their static
// JS/CSS assets - so re-opening an already-visited page while offline shows
// that same page instead of a browser error.
//
// What this NEVER caches: anything under /api/ (session-sensitive,
// must always be live), and no Qur'an/Hadith/Tafsir content is pre-cached
// or bundled here - there is none to cache (this dev environment's database
// has no imported corpus), and caching real Islamic source text offline
// would need its own licensing review before being added.
const CACHE_NAME = "woi-shell-v1";

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))),
    ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Never intercept API calls, cross-origin requests, or non-GET requests.
  if (event.request.method !== "GET") return;
  if (url.origin !== self.location.origin) return;
  if (url.pathname.includes("/api/")) return;

  // Page navigations: try the network first (so signed-in state and fresh
  // content are always preferred); fall back to the last cached copy of
  // that exact page only when the network is unreachable.
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
          return response;
        })
        .catch(() =>
          caches.match(event.request).then((cached) => cached || caches.match(self.registration.scope)),
        ),
    );
    return;
  }

  // Static build assets (_next/static/**): cache-first, since each file's
  // URL already includes a content hash and never changes meaning.
  if (url.pathname.includes("/_next/static/")) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        if (cached) return cached;
        return fetch(event.request).then((response) => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
          return response;
        });
      }),
    );
  }
});
