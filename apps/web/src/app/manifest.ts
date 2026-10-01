import type { MetadataRoute } from "next";

// Installable app-shell metadata. The service worker (public/sw.js) caches only page layout and build assets; the
// Qur'an's Arabic text becomes available offline only when the reader downloads it on the Offline page
// (IndexedDB, see src/lib/offline.ts). See docs/deployment/offline.md.
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "World of Islam",
    short_name: "World of Islam",
    description: "Revelation, knowledge and guidance, connected.",
    start_url: ".",
    display: "standalone",
    background_color: "#0a0908",
    theme_color: "#0a0908",
    icons: [{ src: "icon.svg", sizes: "any", type: "image/svg+xml" }],
  };
}
