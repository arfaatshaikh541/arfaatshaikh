"use client";
import { useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { flushQueue, isOfflineStorageAvailable } from "@/lib/offline";

// Replays actions queued while offline as soon as the browser reports a connection.
export function OfflineSync() {
  useEffect(() => {
    if (!isOfflineStorageAvailable()) return;
    const flush = () => { void flushQueue((path, init) => apiFetch(path, init)).catch(() => undefined); };
    window.addEventListener("online", flush);
    if (navigator.onLine) flush();
    return () => window.removeEventListener("online", flush);
  }, []);
  return null;
}
