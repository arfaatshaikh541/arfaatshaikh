# Project images

`src/data/projects.ts` includes an `image` field per project (e.g. `/images/projects/rafana.svg`) for future use, but no image files exist yet — the Projects hub and detail pages (`src/app/projects/`) intentionally render project identity through typography only, so nothing is broken by their absence.

To add real project imagery:

1. Drop optimized images here, named to match each project's `image` path in `src/data/projects.ts` (e.g. `rafana.svg`, `ai-engagement.svg`, `gridkeep.svg`) — swap the extension for whatever format you actually use (`.jpg`/`.png`/`.webp` are all fine, just update the path in the data file to match).
2. In `src/app/projects/page.tsx` and `src/app/projects/[slug]/page.tsx`, render the image with `next/image` (`fill` + a sized wrapper, or explicit `width`/`height`), including descriptive `alt` text — never decorative/empty `alt` for project screenshots, since they're meaningful content.
