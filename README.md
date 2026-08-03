# Arfaat Shaikh — Creative Engineer Portfolio

A Next.js portfolio for Arfaat Shaikh (Creative Engineer, founder of GRIDKEEP). The centrepiece is a custom-shaded WebGL hero object — a cracked, heartbeat-pulsing metal shell over a real authored model — built with Three.js, React Three Fiber, and GSAP. The homepage is a standard stacked-sections layout (static hero → about → featured work → services → founder → GRIDKEEP → capabilities → philosophy → tech stack → contact) rather than a scroll-jacked narrative, so content is fully server-rendered and indexable without depending on scroll position or JS execution — see "SEO" below.

## Stack

- **Next.js 16** (App Router, Turbopack, React 19) + TypeScript
- **Tailwind CSS v4** — design tokens defined as CSS variables in `src/app/globals.css`
- **Three.js / React Three Fiber / drei** — the 3D sphere system
- **Custom GLSL shaders** — shell, plasma core, and fire, hand-written (no shader libraries)
- **@react-three/postprocessing** — Bloom, Vignette, Chromatic Aberration, plus a custom heat-distortion `Effect`
- **GSAP + ScrollTrigger** — drives the sphere's state and the hero copy from scroll position
- **Lenis** — smooth scrolling (disabled automatically for `prefers-reduced-motion`)
- **Framer Motion** — used narrowly, for the mobile menu's enter/exit transition
- **next/font** — self-hosted Inter, Big Shoulders, and JetBrains Mono (no runtime calls to Google Fonts)

## Getting started

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The dev server uses Turbopack (Next.js 16 default).

```bash
npm run build   # static export (Turbopack) -> writes the out/ folder
npm run start   # preview the exported out/ folder locally (via `serve`)
npm run lint    # ESLint (flat config, eslint-config-next)
```

The site builds as a **static export** (`output: "export"` in `next.config.ts`) — `npm run build` produces a self-contained `out/` folder of plain HTML/CSS/JS that can be uploaded to any host, including shared hosting with no Node.js server (see "Deployment" below). There is no `next start`/Node server mode; `npm run start` just serves the exported folder for local preview.

## Architecture

```
src/
  app/                     Routes (App Router). See "Routes" below.
  components/
    layout/                Root layout chrome: SmoothScrollProvider, Footer
    navigation/             Nav (desktop + mobile), ScrollProgress, SocialRail, SectionRail
    sections/               Homepage + shared page sections (Hero, AboutSnapshot, ServiceOverview, ...)
    three/                  The 3D sphere system (see below)
    ui/                     PageHeader, Breadcrumbs, CtaLink
    seo/                    JsonLd (renders structured data <script> tags)
    forms/                  ContactForm
  data/                    Typed content: services.ts, projects.ts, insights.ts, heroChapters.ts,
                           techStack.ts, process.ts
  lib/                     seo.ts (metadata builder), schema.ts (JSON-LD builders), sceneStore.ts,
                           contact.ts (shared form validation), utils.ts
  shaders/                 Raw .glsl source, imported via a Turbopack raw-loader rule
  types/                   Shared TypeScript types + the *.glsl module declaration
public/
  .htaccess                Apache config for static hosting (404 page, MIME types, caching)
  contact-handler.php      Contact form backend for static export (see "Contact form" below)
  textures/, models/, images/projects/   Placeholder folders with their own READMEs documenting
                                          exactly what to drop in and where to wire it up
```

### Persistent chrome (`src/components/navigation/`)

`SocialRail.tsx` and `SectionRail.tsx` are fixed-position elements mounted globally in `layout.tsx` (left edge: a "Scroll" label + email icon; right edge: a numbered Home/About/Services/Projects/Contact quick-nav that highlights the current section). Both are hidden below the `2xl` breakpoint — `container-edge`'s padding is capped at `5rem`, and the rails need that full margin to clear wide grid content (e.g. `/tech-stack`'s two-column cards) without overlapping it, so they only show once the viewport is wide enough to guarantee the gap. `SocialRail` only renders an email icon, deliberately — LinkedIn/GitHub/Instagram icons would need real profile URLs, and (per this project's brief) nothing gets invented, dead `#` links included.

### The 3D hero system (`src/components/three/`)

The hero object is layered, not a single mesh. It's mounted today by `src/components/sections/Hero.tsx`, a static, normal-flow section (text and a bounded canvas side by side, `<h1>` server-rendered like any other page) — not a scroll-jacked full-viewport pin. That means `sceneState`'s chapter-driven fields (`coreBrightness`, `turbulence`, `shellOpen`, etc., referenced throughout this section) simply sit at their constant module-level defaults from `src/lib/sceneStore.ts` for the whole visit; only `hoverIntensity`, `pulseStrength`, and gyro/pointer parallax actually change at runtime by default. The scroll-narrative wiring described below (`ChapterScroll.tsx` + `heroChapters.ts`) still exists and still works — it's just not what the homepage renders — kept in case a future page wants that treatment instead of, or alongside, the static hero.

- **`CoreModel.tsx`** — the primary visual: a real authored model (`public/models/hero-core.glb`, ~32k triangles / 1.48 MB after optimization — see that folder's README for the full pipeline), loaded with `@react-three/drei`'s `useGLTF` inside a `<Suspense>` boundary. On load it recenters the mesh on its own geometry bounding box (the export's pivot sits at the bottom, not the visual center), normalizes its scale, pulls the baked material's metalness/roughness down from fully-metallic (which reads as near-black without an environment map — this scene is lit with direct lights only, no HDRI, to stay self-contained) to values that catch the scene's lights directly, and reuses its own basecolor texture as an `emissiveMap` so the painted-on cracks glow. That glow isn't a flat brightness value: a sharp, asymmetric "heartbeat" pulse (`Math.sin(...)` cubed, so it spends most of its time dark and spikes bright and fast rather than breathing smoothly) drives `emissiveIntensity` every frame, with both its speed and punch ramping up with scroll turbulence, hover, and click — calm at rest, increasingly frantic like it's straining toward detonation deeper into the more intense chapters. A faint scale throb in lockstep with the same heartbeat makes the whole object physically pulse on each beat. Also responds to `pulseStrength` (scale kick), `bladeOpen` (a subtle swell), and `splitAmount` (fades out for the Contact chapter's climax).
- **`Flames.tsx`** / **`PlasmaColumn.tsx`** — camera-facing (`Billboard`) planes using hand-written `fireVertex.glsl` / `fireFragment.glsl`: noise-based flame shapes, additive blending, per-flame random flicker. Flame jets sit at five fixed directions around the model and push further outward as `sceneState.separation` increases in the more turbulent chapters.
- **`ElectricArcs.tsx`** — 6 procedural lightning bolts arcing around the core, generated with classic recursive midpoint displacement and re-rolled every ~90ms for a flicker (not a smooth glide). Reach grows with `sceneState.shellOpen`; intensity scales with scroll turbulence, hover, and click pulses.
- **`Particles.tsx`** — two `THREE.Points` fields (smoke + embers) sharing one canvas-generated soft-dot texture (no external image), with lower counts on narrow viewports.
- **`OrbitRings.tsx`** — segmented (non-continuous) rings with small emissive nodes for the Cloud/DevOps chapter — deliberately not a "Saturn ring."
- **`Pedestal.tsx`** — a glowing platform beneath the hero object: concentric flat rings, a ring of tick marks, and a beam (a flipped, re-centered `ConeGeometry` so its sharp point touches the platform and it widens going back up toward the model) — all `meshBasicMaterial` with additive blending, no textures or shaders. Sits as a sibling in `SphereRig`'s rotating group (not nested inside `CoreModel`'s own scaled group), so it stays a fixed offset below the model regardless of the model's own heartbeat/swell scale animation.
- **`HoverPulseController.tsx`** — an invisible (opacity-0 but still raycastable) hit-test sphere using r3f's built-in pointer events for hover (ramps `sceneState.hoverIntensity`) and click (a GSAP "energy pulse": a quick spike in `sceneState.pulseStrength` plus a small camera punch-in via `pulseZOffset`), both consumed by the model, flames, arcs, lights, and bloom.
- **`Lighting.tsx`** — ambient + two directional key lights (one warm rim fill) + two flickering internal red point lights + a rim light, all boosted by hover/pulse alongside `coreBrightness`.
- **`HeroEnvironment`** (in `SphereScene.tsx`) — a fully procedural reflection environment via `@react-three/drei`'s `<Environment>` + `<Lightformer>`: a warm rect panel and a cool thin strip baked into a small PMREM cubemap entirely at runtime (`resolution={128}`, `background={false}`), no HDRI file and no network fetch. This is what gives `CoreModel`'s metal blades real specular reflections instead of only flat direct-light highlights — `material.envMapIntensity` on the model is dialed down from the default 1.0 so it reads as reflective without washing out the emissive glow.
- **`PostFX.tsx`** — `EffectComposer` with Bloom, Chromatic Aberration, Vignette, and `effects/HeatDistortionEffect.ts` (a hand-written `postprocessing` `Effect` subclass, registered via `extend()` and given a direct `ref`, mutated in `useFrame` — see note below on why it's *not* driven through `wrapEffect`+`ref`). Bloom's `luminanceThreshold` is tuned high enough (0.32) that only the crack glow and hot highlights trigger it, not the whole lit surface, so the heartbeat pulse reads as a sharp flare rather than a general wash. A `DepthOfField` pass was tried here and pulled — it renders fine in dev but its mask pass throws `GL_INVALID_OPERATION: glBlitFramebuffer: Depth/stencil buffer format combination not allowed for blit` on at least one real GPU/driver + production-build combination, which silently drops the entire hero model from the frame. Not worth the risk for a subtle background-blur effect; re-evaluate only with a broader compatibility test across real devices, not just one environment.
- **`CameraRig.tsx`** — lerps the camera position/lookAt toward `sceneState` every frame (including the pulse punch-in), plus mouse parallax on fine-pointer devices and **gyroscope parallax on touch devices** (`deviceorientation`, calibrated against the phone's initial resting angle; on iOS 13+ the permission prompt is requested on the visitor's first tap, since it can only be triggered from a user gesture). Both feed the same pointer signal, and both are skipped under `prefers-reduced-motion`.
- **`SphereScene.tsx`** — the `<Canvas>` root: DPR capped via `dpr={[1, 2]}` (lower on `PerformanceMonitor` decline), `frameloop` set to `"never"` when the tab is hidden, WebGL-support detection, and an `ErrorBoundary` that renders `SphereFallback.tsx` (a CSS-only radial-gradient sphere) if anything throws.
- **`SphereCanvasLazy.tsx`** — `next/dynamic(..., { ssr: false })` wrapper so the Canvas never touches the server render and the JS is code-split from the initial bundle.

An earlier iteration built the shell, core, and blades as hand-written GLSL shaders and procedural geometry (no external assets at all, since no authored model existed yet) — that code is gone now that a real sculpted model is in place, but `src/shaders/` still has `fireVertex.glsl` / `fireFragment.glsl` / `noise.glsl` for the flame jets and plasma column, which remain fully procedural.

**`sceneState`** (`src/lib/sceneStore.ts`) is a plain mutable object, deliberately *not* React state — it's read every frame in `useFrame`, and routing 60fps updates through React would be wasted re-renders. Hover, click, and gyro/pointer parallax all write to this *same* object, so they compose rather than conflict: a click pulse spikes `pulseStrength` on top of whatever `hoverIntensity` already is, and both feed into the model's heartbeat, the flames, the arcs, the lights, and bloom simultaneously.

**Scroll wiring (dormant by default)** — `ChapterScroll.tsx` + `heroChapters.ts`: `CHAPTER_STATES` holds one target snapshot of `sceneState` per chapter (dormant → awakening → AI → automation → software → cybersecurity → cloud → GRIDKEEP → contact). A `ScrollTrigger` spanning a full-viewport sticky wrapper calls `applyChapterProgress(progress, CHAPTER_STATES)` on every scroll tick, lerping between the two nearest snapshots so the object transforms continuously rather than snapping between fixed states, with each chapter's copy as a stacked, absolutely-positioned layer whose opacity/translate are set from the same scroll callback. This is a complete, working alternative to the static `Hero.tsx` — swap which one a page renders to get the cinematic scroll-narrative treatment back — but nothing on the current site calls `applyChapterProgress`, so `CHAPTER_STATES`' non-interaction fields never actually change today.

**Why a raw-loader rule instead of importing `.glsl` as JS strings directly:** Turbopack (Next 16's default bundler) doesn't parse arbitrary file extensions out of the box. `next.config.ts` adds a `turbopack.rules` entry mapping `*.glsl` to `raw-loader` (an officially Turbopack-supported webpack loader) so every shader can live in its own real `.glsl` file and still be imported as a plain string in TypeScript — see `src/types/glsl.d.ts` for the matching module declaration.

**Why `HeatDistortionEffect` is registered with `extend()` instead of `@react-three/postprocessing`'s `wrapEffect`:** `wrapEffect`'s generated component is a plain (non-`forwardRef`) function that spreads its rest props — including `ref` itself — into `JSON.stringify(props)` as a `useMemo` dependency. Under React 19, a `ref` passed to a non-forwardRef function component is delivered as a normal prop, so once that ref is attached to a real Three.js/Effect instance (which has circular `parent`/`children` references), `JSON.stringify` throws on the next render. The built-in effects (`Bloom`, `Vignette`, `ChromaticAberration`) are therefore driven by *props*, quantized and only re-emitted when they cross a small threshold (see `PostFX.tsx`) instead of by ref-mutation, to avoid both the crash and needless full effect-instance reconstruction on every frame. The custom heat-distortion effect sidesteps the whole issue by being registered directly via `extend()` and rendered as a normal host element (`<heatDistortionEffect ref={...} />`), which r3f refs correctly.

## Routes

```
/                          Homepage (static hero + about/value tiles + featured work + standard sections)
/about
/services                  Hub
/services/[slug]           ai-automation · software-saas · cybersecurity · cloud-devops · web-experiences
/projects                  Hub
/projects/[slug]           rafana-digital-platform · ai-customer-engagement-platform · gridkeep-digital-experience
/gridkeep
/insights                  Hub
/insights/[slug]           6 original articles
/tech-stack                Full technology stack by category
/process                   How an engagement actually runs, step by step
/contact                   Form -> public/contact-handler.php (see "Contact form" below)
/privacy
/terms
/sitemap.xml, /robots.txt, /opengraph-image   Generated statically (see src/app/)
```

`/services/[slug]`, `/projects/[slug]`, and `/insights/[slug]` are statically generated at build time via `generateStaticParams` from the corresponding file in `src/data/`; unknown slugs call `notFound()`.

## Content

All page copy lives in typed data files under `src/data/` — `services.ts`, `projects.ts`, `insights.ts`, `heroChapters.ts`, `techStack.ts`, `process.ts`, `capabilities.ts`, `valueProps.ts` — so content changes never require touching a page template. Per the brief, nothing invented: no fake metrics, testimonials, client logos, awards, or years of experience. Project statuses use honest labels (`Concept` / `In Development` / `Internal Product` / `Client Platform`). The homepage's "About Me" band (`AboutSnapshot.tsx`) makes this concrete: instead of a stat row of made-up numbers (years of experience, project counts, client counts), its four tiles (`valueProps.ts`) are qualitative capability claims — "Full-Stack," "AI-Native," and so on — that don't assert anything unverifiable.

## SEO

- Per-page `Metadata` via `buildMetadata()` (`src/lib/seo.ts`): unique title/description, canonical URL, Open Graph + Twitter card.
- JSON-LD via `<JsonLd />` + builders in `src/lib/schema.ts`: `Person` (with `knowsAbout` listing the real capabilities from `src/data/capabilities.ts`), `Organization` (with a `hasOfferCatalog` of real services from `src/data/services.ts`), `WebSite` (all three global, in `layout.tsx`), plus per-page `ProfilePage`, `Service`, `BreadcrumbList`, `Article`, `FAQPage`, `ContactPage`, `CreativeWork`, and a generic `itemListSchema()` used on the homepage for its services and featured-projects lists.
- `src/app/sitemap.ts` and `src/app/robots.ts` (Next.js file-convention, generate real `sitemap.xml` / `robots.txt`) — every real route, including dynamic service/project/article slugs and `/tech-stack` and `/process`.
- `src/app/opengraph-image.tsx` generates a real branded PNG (via `next/og`) as the default social preview image for any page that doesn't set its own.
- The homepage hero (`Hero.tsx`) is a normal server-rendered section — a real `<h1>`, paragraph, and links in the initial HTML, with the WebGL canvas as a `next/dynamic(..., { ssr: false })` chunk beside it rather than something the text is painted over. That's a deliberate Core Web Vitals choice as much as an SEO one: the LCP candidate is text that's already in the document, not gated behind a canvas boot, and there's no `ScrollTrigger`-pinned multi-viewport-height wrapper on the homepage doing layout/scroll work on every tick.
- All 3D-hero copy (headlines, descriptions, CTAs) is real HTML — nothing meaningful is locked inside WebGL, on either the static `Hero.tsx` or the dormant `ChapterScroll.tsx` alternative.

## Contact form

The site is a static export with no Node.js server available at runtime, so `src/components/forms/ContactForm.tsx` posts to a **PHP** handler rather than a Next.js API route: `public/contact-handler.php` (copied into `out/` — and therefore your web root — automatically since it lives in `public/`).

- Shared validation logic in `src/lib/contact.ts` is mirrored field-for-field in the PHP script (required fields, email format, message length, consent checkbox) so both stay in sync if you change the rules.
- A hidden honeypot field (`website`) — a filled value is rejected as spam server-side without revealing the honeypot to the client.
- A file-based sliding-window rate limiter (5 requests / 10 minutes per IP), stored under the system temp directory since shared hosting has no Redis/KV available by default.
- Delivery uses PHP's built-in `mail()`, sent to the address in `$recipientEmail` at the top of the script (defaults to `hello@arfaat.com` — **update this**). Before going live, also check the `From:` header comment in the script: many hosts, including IONOS, reject or spam-flag mail sent "from" an address that isn't a real mailbox on your own domain. If plain `mail()` proves unreliable, swap the send step for [PHPMailer](https://github.com/PHPMailer/PHPMailer) over your IONOS SMTP credentials — the script has a comment marking exactly where.

If you ever move to a Node-capable host (Vercel, IONOS Deploy Now, a VPS), you can trivially reintroduce a Next.js API route (`src/app/api/contact/route.ts`) using the same `src/lib/contact.ts` validators, point `CONTACT_ENDPOINT` in `ContactForm.tsx` back at it, and drop `output: "export"` from `next.config.ts`.

## 3D and image assets

`public/models/hero-core.glb` is the one real binary 3D asset the site depends on — see `public/models/README.md` for exactly what it is, how it was optimized (941k triangles / 29.6 MB down to ~32k triangles / 1.48 MB), and what shape a replacement needs to have. `public/textures/` and `public/images/projects/` each have their own README explaining what's still procedural (flames, smoke, embers — all generated at runtime, no files needed) versus what's an open slot for real imagery (project screenshots) if you want to add them later.

## Performance & resilience notes

- `SphereScene` caps `devicePixelRatio` to `[1, 2]` and drops to `[1, 1.25]` on `PerformanceMonitor` decline.
- Particle counts in `Particles.tsx` are halved below a 768px viewport.
- The Canvas's `frameloop` is set to `"never"` while the tab is hidden (`visibilitychange`).
- If WebGL isn't available, or the Canvas throws for any reason, `SphereFallback.tsx` (a CSS radial gradient) renders instead — the fallback is also what's shown momentarily while the Canvas code-splits in.
- `prefers-reduced-motion` disables Lenis smooth scrolling, camera parallax, and shortens the mobile menu / chapter-copy transitions.

## Deployment

The site builds to a static `out/` folder, so it can be uploaded to **any** web server that serves plain files — no Node.js required at runtime. Before your first deploy, update `siteConfig.url` / `email` / `gridkeepUrl` in `src/lib/seo.ts` and `$recipientEmail` in `public/contact-handler.php` if they should be different — canonical URLs, the sitemap, JSON-LD, and where contact-form enquiries are emailed all derive from these.

### Deploying to IONOS shared hosting (FTP)

1. **Build the export:**
   ```bash
   npm run build
   ```
   This produces an `out/` folder containing the entire site as static HTML/CSS/JS, plus `contact-handler.php` and a `.htaccess` (404 page, correct MIME type for the generated OpenGraph image, and long-term caching for hashed build assets).

2. **Find your FTP credentials.** In the IONOS control panel, go to your hosting package → **FTP Access** (or **File Manager** if you'd rather upload through the browser instead of an FTP client). Note the host, username, and password (or the port for SFTP, if your package offers it).

3. **Connect with an FTP client** — [FileZilla](https://filezilla-project.org/) is the common free choice:
   - Host: the FTP host IONOS gave you (often `ftp.yourdomain.com` or an `access-…` hostname from the control panel)
   - Username / password: from step 2
   - Port: `21` for FTP, `22` for SFTP if offered

4. **Upload the *contents* of `out/`** (not the `out` folder itself) into your webspace's document root — usually a folder named `/` or `htdocs`/`clickandbuilds`-style depending on your package; check the control panel for the exact path if it isn't the top level. This means `out/index.html`, `out/.htaccess`, `out/_next/`, `out/about/`, `out/contact-handler.php`, etc. should all sit directly inside that root folder, not inside a nested `out/` subfolder.
   - **Make sure your FTP client shows and transfers dotfiles** — `.htaccess` is easy to miss since some clients hide dotfiles by default. Without it, the custom 404 page and OpenGraph image MIME type won't work (the rest of the site is unaffected).
   - Uploading ~500 small files over FTP can take a few minutes; that's normal.

5. **Set the contact form's recipient.** Before (or right after) uploading, open `public/contact-handler.php` locally, set `$recipientEmail` to a real inbox on your domain, rebuild, and re-upload just that one file if you change it after the fact.

6. **Verify:**
   - Visit your domain — the homepage and 3D sphere should load.
   - Visit a route that doesn't exist (e.g. `/asdf`) — you should see the on-brand 404 page, not a generic Apache error. If you see the generic error instead, `.htaccess` didn't upload — check step 4.
   - Submit the contact form with real details and confirm the email arrives. If it doesn't, see the "Contact form" section above about the `From:` header / SMTP.
   - Check `/sitemap.xml` and `/robots.txt` load correctly.

7. **SSL / HTTPS:** enable it from the IONOS control panel (usually a free Let's Encrypt certificate you can toggle on per domain) rather than through `.htaccess` — that keeps it in sync with IONOS's own renewal process.

### Updating the live site later

Every time you change content or code: `npm run build` locally, then re-upload the changed files from `out/` (most FTP clients can sync/only-upload-changed-files). Files inside `_next/static/` are content-hashed and safe to leave in place indefinitely; everything else (the `.html` files, `sitemap.xml`, etc.) should be replaced on each deploy.

### Other hosts

Because it's a static export, the same `out/` folder also deploys as-is to Vercel, Netlify, Cloudflare Pages, GitHub Pages, an S3+CloudFront bucket, or a VPS behind nginx — none of that requires the IONOS-specific PHP/FTP steps above. If you move to a platform that *can* run Node.js and want the contact form to run through a real Next.js API route again instead of PHP, see the note at the end of the "Contact form" section.
