import type { MetadataRoute } from "next";

// Installable app-shell metadata. Deliberately does not declare any content
// (Qur'an/Hadith/Tafsir) as "available offline" - the service worker
// (public/sw.js) caches only the shell and previously-visited pages, never
// any Islamic knowledge content, which this dev environment has none of
// anyway. See docs/deployment/offline.md.
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
