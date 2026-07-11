# GRIDKEEP

A founder-led technology systems company — AI, automation, custom software, cybersecurity, cloud infrastructure, business systems, and immersive web experiences. This repository is the full production website: a 3D-driven, scroll-choreographed Next.js application.

Live concept: **https://gridkeep.com** · Founder: **Arfaat Shaikh** · Based in the **United Arab Emirates**.

---

## Stack

- **Next.js 15** (App Router, TypeScript, static generation wherever possible)
- **React 19** (required — see [React 19 requirement](#react-19-requirement) below)
- **React Three Fiber v9 + Three.js + drei v10** for all 3D scenes
- **Custom GLSL shaders** (no external shader libraries) for energy glow, scanlines, portal distortion, data pulses, and smoke
- **@react-three/postprocessing** (Bloom, Vignette, Noise, desktop-only DepthOfField)
- **GSAP + ScrollTrigger** for scroll-driven camera/scene state
- **Lenis** for smooth scrolling (disabled automatically under `prefers-reduced-motion`)
- **Framer Motion** for lightweight UI reveals
- **Tailwind CSS** for the design system
- **gray-matter + remark** for a Markdown-based Insights (articles) system
- **next/font** (self-hosted at build time — no runtime font requests)

## Getting started

```bash
npm install
npm run dev
```

Visit `http://localhost:3000`.

```bash
npm run build   # production build
npm run start   # serve the production build
npm run lint    # ESLint
npm run typecheck
```

Copy `.env.example` to `.env.local` if you want to configure the contact form recipient before wiring real email delivery (see [Contact form](#contact-form) below).

---

## Architecture

```
src/
  app/                  Route tree (App Router) — every page has unique metadata + JSON-LD
  components/
    layout/              Header, Footer, SmoothScroll (Lenis), SkipLink
    navigation/          Mega menu, mobile nav, scroll progress
    sections/             Homepage chapters + shared PageHero/Breadcrumbs
    three/
      scenes/            The 10 signature 3D prototypes (Core, Neural, Assembly,
                         Architecture, Vault, Orbit, WebLab, Network, Command, Portal)
      materials.tsx      Custom shaderMaterial definitions, registered via `extend()`
      SceneCanvas.tsx    Shared Canvas: postprocessing, DPR cap, WebGL gate, pause-on-hidden
      ChapterScene.tsx   Client-only lazy wrapper (see below) + CSS poster fallback
    forms/               Contact form (client + shared validation)
    seo/                 JSON-LD + breadcrumbs
  data/                  services.ts, projects.ts, industries.ts, formOptions.ts
  content/insights/      Markdown articles (frontmatter + body)
  lib/                   seo.ts, schema.ts, insights.ts, gsapSetup.ts, performance.ts, three.ts
  shaders/               Raw GLSL as TypeScript template strings, grouped by purpose
```

### 3D scene architecture — a deliberate scope decision

The brief called for one unbroken, single-canvas cinematic film with a master camera
rig threading through all ten prototypes. That is achievable, but it concentrates all
WebGL cost into one always-mounted context and makes the camera math the single
highest-risk part of the build. Instead, **each chapter mounts its own scene**, driven
by `useScrollProgress` (a GSAP ScrollTrigger scrubbed against that chapter's own
section) and unmounted once it's off-screen. This is the same pattern used by most
production scroll-heavy WebGL sites (fixed/sticky canvas behind scrolling DOM text,
per-section). It keeps every route's WebGL cost bounded, lets `/services/[slug]` pages
reuse the exact same scene component the homepage chapter uses, and avoids a single
giant scene graph that has to be fully loaded before anything appears.

Every prototype (`src/components/three/scenes/*.tsx`) is **fully procedural** — built
from Three.js primitives, instancing, and the shared shader materials in
`materials.tsx`. There are no external `.glb`/`.gltf` model files: nothing was sourced
from a stock library, and the whole 3D layer stays buildable without a binary asset
pipeline. `useOrbitingInstances` and `EdgeBeam` are small shared helpers reused across
scenes (orbiting debris/nodes, and the "orange energy line between two points" motif
that recurs across Neural, Orbit, Network, and Command).

Each scene component accepts a `progressRef` (0→1, written by GSAP outside React's
render loop for performance) and reacts to it inside `useFrame` — shell opening,
particle assembly, threat containment, module locking, etc. — matching the
interaction described in the brief for that prototype.

### React 19 requirement

**Next.js 15's App Router client runtime is built against React 19 internally**
(`next/dist/compiled/react`), independent of what a project declares in
`package.json`. `@react-three/fiber` v8 targets React 18's reconciler internals
(`__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED`), which React 19 restructured —
mixing fiber v8 with Next 15 crashes the WebGL layer with a
`ReactCurrentBatchConfig`/`ReactCurrentOwner` error the moment a `<Canvas>` mounts.
This project pins **React 19** and **`@react-three/fiber` v9** (built for React 19)
for exactly this reason. If you ever downgrade Next.js to the 14.x line, downgrade
React and `@react-three/fiber` to the matching 18.x generation together — don't mix
major versions across that boundary.

### Performance & degradation

- `SceneCanvas` caps `devicePixelRatio`, disables `frameloop` when the tab is hidden,
  and skips `DepthOfField` on mobile.
- `usePrefersReducedMotion` / `useIsMobile` (in `lib/performance.ts`) scale particle
  counts down and disable Lenis + postprocessing bloom under reduced motion.
- `WebGLGate` + `SceneErrorBoundary` fall back to a CSS gradient `ScenePoster` (per
  scene, no image assets required) if WebGL is unavailable or a scene throws.
- 3D scenes are loaded via `next/dynamic({ ssr: false })` — React Three Fiber's
  reconciler cannot be server-rendered safely inside Next's prerendering pass, so the
  poster is what's in the initial HTML, and the real scene hydrates client-side. All
  SEO-relevant copy lives in plain semantic HTML outside the canvas, never inside it.

---

## SEO

- Every route has a unique `<title>`, description, canonical URL, and Open Graph /
  Twitter metadata via `lib/seo.ts#buildMetadata`.
- Structured data (`lib/schema.ts`) covers Organization, WebSite, WebPage, Service,
  BreadcrumbList, Article, ContactPage, CreativeWork, SoftwareApplication, and
  FAQPage, injected per-page via `<JsonLd>`.
- `app/sitemap.ts` and `app/robots.ts` are generated from the same data files that
  drive the routes (services, projects, insights) — no hand-maintained URL lists that
  can drift out of sync.
- `app/opengraph-image.tsx` and `app/icon.tsx` generate real OG/favicon images at
  request time via `next/og`, no static art asset required.
- Almost every route is fully static or SSG'd (see `npm run build` output) — only
  `/api/contact` and the two `next/og` image routes are dynamic.

## Accessibility

- Skip-to-content link, visible focus states, semantic headings/landmarks throughout.
- Mobile nav is a focus-trapped, `Escape`-closable dialog; the services mega menu is a
  simple disclosure pattern reachable and closable by keyboard.
- `prefers-reduced-motion` is respected app-wide: Lenis doesn't initialize, GSAP
  scroll-linked camera motion stays static, Framer Motion reveals skip their
  offset/animation.
- No content that matters for understanding the page exists only inside the WebGL
  canvas — every canvas is decorative/illustrative of copy that exists in real HTML
  next to it.

## Contact form

`src/components/forms/ContactForm.tsx` + `src/app/api/contact/route.ts`.

- Shared validation (`lib/contactValidation.ts`) runs both client-side (before submit)
  and server-side (in the API route) — the client check is a UX nicety, not the
  security boundary.
- A hidden honeypot field silently accepts bot submissions without erroring.
- The API route includes an in-memory rate limiter (documented in-code as a
  per-instance limiter — swap in a shared store like Upstash Redis for real
  multi-instance rate limiting in production).
- **Email delivery is a documented placeholder** (`deliverContactSubmission` in the
  API route): it currently logs the submission. Wire it to a transactional email
  provider (Resend, Postmark, or SMTP via nodemailer) using environment variables —
  see `.env.example`. `CONTACT_EMAIL` in `lib/constants.ts` is the single source of
  truth for the address shown across the site (`hello@gridkeep.com`).

## Insights (content system)

Articles live as Markdown files with frontmatter in `content/insights/*.md`, parsed
at build/request time by `lib/insights.ts` (gray-matter + remark). Adding an article
is just adding a `.md` file — no code changes required; `/insights` and
`/insights/[slug]` both derive their routes and related-article logic from the same
loader.

---

## Deployment

### Vercel (recommended)

This is a standard Next.js App Router project — connect the repository in Vercel and
deploy with the default settings. The contact API route, `next/og` images, and all
static/SSG pages work out of the box.

### Any Node.js host (including an IONOS VPS)

```bash
npm run build
npm run start   # starts a Node server on $PORT (default 3000)
```

Put this behind a reverse proxy (nginx/Caddy) for TLS. This preserves the contact API
route and dynamic OG images.

### IONOS shared/static webspace

IONOS's plain shared-hosting webspace serves static files only — it cannot run a
Node.js server or the `/api/contact` route as-is. This project intentionally does
**not** ship a static export (`next export`/`output: "export"`) as the default,
because the API route and the two `next/og` image routes require a server runtime and
would silently break under a static export.

To deploy to static IONOS webspace, do one of the following first:

1. **Swap the contact form's destination.** Point `ContactForm` at an external
   form-processing endpoint you control (a small serverless function on another
   host, or a transactional-email API called directly from the client with a
   restricted key) instead of `/api/contact`, then set `output: "export"` in
   `next.config.mjs` and run `next build` — the output in `out/` is plain static
   files you can upload via IONOS's file manager or FTP.
2. **Or keep `/api/contact`** and deploy to IONOS's **Node.js hosting** plan (not the
   static webspace plan), using the "any Node.js host" instructions above.

Either way, `next/og` image routes (`opengraph-image.tsx`, `icon.tsx`) would need to
be replaced with static image files before a static export, since `ImageResponse`
requires the Edge/Node runtime.

---

## What's deliberately scoped down

In the interest of shipping something real, buildable, and verified end-to-end rather
than a larger set of half-finished pieces, a few things from the original brief were
scoped down. Noted here rather than silently:

- The ten prototypes are genuinely distinct procedural scenes with their own geometry,
  particle behavior, and scroll-driven state changes — but they are not hand-modeled,
  DRACO-compressed GLB assets (there are none to source), and postprocessing is
  shared/tuned per-canvas rather than using a fully custom selective-bloom layer per
  object.
- The homepage is a per-chapter scene architecture (see above) rather than one
  continuous master canvas with a single camera rig threading all ten prototypes.
- `/industries` is a single index page (as listed in the requested route table); there
  is no `/industries/[slug]` route since none was specified.
