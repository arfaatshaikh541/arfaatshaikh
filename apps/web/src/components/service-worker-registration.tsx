"use client";
import { useEffect } from "react";

// Registers the minimal app-shell service worker (public/sw.js) at the
// deployment's actual base path (NEXT_PUBLIC_WOI_BASE_PATH, mirrored from
// WOI_BASE_PATH in next.config.ts) so it works identically whether the app
// is served at "/" or under "/worldofislam".
export function ServiceWorkerRegistration() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    const basePath = process.env.NEXT_PUBLIC_WOI_BASE_PATH ?? "";
    navigator.serviceWorker.register(`${basePath}/sw.js`, { scope: `${basePath}/` }).catch(() => {
      // Registration failure (e.g. insecure context in some dev setups) is
      // non-fatal - the app works fully online-only without it.
    });
  }, []);
  return null;
}
