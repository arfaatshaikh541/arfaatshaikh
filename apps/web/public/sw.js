// Service worker: offline app shell.
//
// Caches (a) the layout of public pages you have visited and (b) hashed build assets, so those pages reopen
// without a connection. It never intercepts API calls, never caches account, admin or authentication pages, and
// never stores religious text: the Qur'an is made available offline only through the explicit download on the
// Offline page, which saves into IndexedDB (see src/lib/offline.ts).
const CACHE_NAME = "woi-shell-v2";
const PRIVATE_PATHS = /\/(dashboard|admin|organisations|login|register|forgot-password|reset-password|verify-email|source-registry)(\/|$)/;

self.addEventListener("install", () => { self.skipWaiting(); });

self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))));
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET") return;
  if (url.origin !== self.location.origin) return;
  if (url.pathname.includes("/api/")) return;
  if (PRIVATE_PATHS.test(url.pathname)) return;

  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response.ok) { const copy = response.clone(); caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy)); }
          return response;
        })
        .catch(() => caches.match(event.request).then((cached) => cached || caches.match(self.registration.scope) || new Response("Offline", { status: 503, headers: { "Content-Type": "text/plain" } }))),
    );
    return;
  }

  if (url.pathname.includes("/_next/static/")) {
    event.respondWith(
      caches.match(event.request).then((cached) => cached || fetch(event.request).then((response) => {
        if (response.ok) { const copy = response.clone(); caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy)); }
        return response;
      })),
    );
  }
});
