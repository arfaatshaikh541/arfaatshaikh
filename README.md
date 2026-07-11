# Arfaat Shaikh — Creative Engineer Portfolio

A cinematic, scroll-driven Next.js portfolio for Arfaat Shaikh (Creative Engineer, founder of GRIDKEEP). The centrepiece is a custom-shaded WebGL sphere — a cracked obsidian shell with a live plasma core — that transforms across nine chapters as the homepage scrolls, built with Three.js, React Three Fiber, and GSAP ScrollTrigger.

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
    navigation/             Nav (desktop + mobile), ScrollProgress
    sections/               Homepage + shared page sections (ChapterScroll, ServiceOverview, ...)
    three/                  The 3D sphere system (see below)
    ui/                     PageHeader, Breadcrumbs, CtaLink
    seo/                    JsonLd (renders structured data <script> tags)
    forms/                  ContactForm
  data/                    Typed content: services.ts, projects.ts, insights.ts, heroChapters.ts
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

### The 3D sphere system (`src/components/three/`)

The sphere is layered, not a single mesh:

- **`SphereShell.tsx`** (rendered twice, at two radii) — a custom `ShaderMaterial` sphere. The fragment shader (`src/shaders/shellFragment.glsl`) carves openings procedurally (no painted-on textures) using signed-angle masks against five fixed directions, softened and made irregular with layered simplex noise (`src/shaders/noise.glsl`), and discards fragments inside them so the layer behind shows through with real depth. The vertex shader (`shellVertex.glsl`) segments the shell into coarse chunks and can displace them outward (`uSeparation`) for the "shattering/defensive" states, plus a `uSplit` uniform that pulls each half apart for the Contact chapter.
- **`SphereCore.tsx`** — a smaller glowing plasma sphere (`coreVertex.glsl` / `coreFragment.glsl`) using fractal Brownian motion noise for turbulence, a Fresnel rim term, and a brightness/turbulence pulse driven by scroll.
- **`Flames.tsx`** / **`PlasmaColumn.tsx`** — camera-facing (`Billboard`) planes using `fireVertex.glsl` / `fireFragment.glsl`: noise-based flame shapes, additive blending, per-flame random flicker.
- **`Particles.tsx`** — two `THREE.Points` fields (smoke + embers) sharing one canvas-generated soft-dot texture (no external image), with lower counts on narrow viewports.
- **`OrbitRings.tsx`** — segmented (non-continuous) rings with small emissive nodes for the Cloud/DevOps chapter — deliberately not a "Saturn ring."
- **`Lighting.tsx`** — ambient + directional key light + two flickering internal red point lights + a rim light.
- **`PostFX.tsx`** — `EffectComposer` with Bloom, Chromatic Aberration, Vignette, and `effects/HeatDistortionEffect.ts` (a hand-written `postprocessing` `Effect` subclass, registered via `extend()` and given a direct `ref`, mutated in `useFrame` — see note below on why it's *not* driven through `wrapEffect`+`ref`).
- **`CameraRig.tsx`** — lerps the camera position/lookAt toward `sceneState` every frame, plus disabled-by-default mouse parallax (off on touch devices and `prefers-reduced-motion`).
- **`SphereScene.tsx`** — the `<Canvas>` root: DPR capped via `dpr={[1, 2]}` (lower on `PerformanceMonitor` decline), `frameloop` set to `"never"` when the tab is hidden, WebGL-support detection, and an `ErrorBoundary` that renders `SphereFallback.tsx` (a CSS-only radial-gradient sphere) if anything throws.
- **`SphereCanvasLazy.tsx`** — `next/dynamic(..., { ssr: false })` wrapper so the Canvas never touches the server render and the JS is code-split from the initial bundle.

**Scroll wiring** (`src/lib/sceneStore.ts` + `src/components/sections/ChapterScroll.tsx`): `sceneState` is a plain mutable object (deliberately *not* React state — it's read every frame in `useFrame`, and routing 60fps updates through React would be wasted re-renders). `CHAPTER_STATES` holds one target snapshot of `sceneState` per chapter (dormant → awakening → AI → automation → software → cybersecurity → cloud → GRIDKEEP → contact). A single `ScrollTrigger` spanning the whole hero wrapper calls `applyChapterProgress(progress, CHAPTER_STATES)` on every scroll tick, which lerps between the two nearest chapter snapshots — so the sphere transforms continuously, not via a snap/fade between fixed states. The hero copy for each chapter is a stacked, absolutely-positioned layer inside the same sticky viewport as the canvas; opacity/translate are set imperatively from the same scroll callback (not React state) for the same performance reason.

**Why a raw-loader rule instead of importing `.glsl` as JS strings directly:** Turbopack (Next 16's default bundler) doesn't parse arbitrary file extensions out of the box. `next.config.ts` adds a `turbopack.rules` entry mapping `*.glsl` to `raw-loader` (an officially Turbopack-supported webpack loader) so every shader can live in its own real `.glsl` file and still be imported as a plain string in TypeScript — see `src/types/glsl.d.ts` for the matching module declaration.

**Why `HeatDistortionEffect` is registered with `extend()` instead of `@react-three/postprocessing`'s `wrapEffect`:** `wrapEffect`'s generated component is a plain (non-`forwardRef`) function that spreads its rest props — including `ref` itself — into `JSON.stringify(props)` as a `useMemo` dependency. Under React 19, a `ref` passed to a non-forwardRef function component is delivered as a normal prop, so once that ref is attached to a real Three.js/Effect instance (which has circular `parent`/`children` references), `JSON.stringify` throws on the next render. The built-in effects (`Bloom`, `Vignette`, `ChromaticAberration`) are therefore driven by *props*, quantized and only re-emitted when they cross a small threshold (see `PostFX.tsx`) instead of by ref-mutation, to avoid both the crash and needless full effect-instance reconstruction on every frame. The custom heat-distortion effect sidesteps the whole issue by being registered directly via `extend()` and rendered as a normal host element (`<heatDistortionEffect ref={...} />`), which r3f refs correctly.

## Routes

```
/                          Cinematic homepage (9-chapter 3D hero + standard sections)
/about
/services                  Hub
/services/[slug]           ai-automation · software-saas · cybersecurity · cloud-devops · web-experiences
/projects                  Hub
/projects/[slug]           rafana-digital-platform · ai-customer-engagement-platform · gridkeep-digital-experience
/gridkeep
/insights                  Hub
/insights/[slug]           6 original articles
/contact                   Form -> public/contact-handler.php (see "Contact form" below)
/privacy
/terms
/sitemap.xml, /robots.txt, /opengraph-image   Generated statically (see src/app/)
```

`/services/[slug]`, `/projects/[slug]`, and `/insights/[slug]` are statically generated at build time via `generateStaticParams` from the corresponding file in `src/data/`; unknown slugs call `notFound()`.

## Content

All page copy lives in typed data files under `src/data/` — `services.ts`, `projects.ts`, `insights.ts`, `heroChapters.ts` — so content changes never require touching a page template. Per the brief, nothing invented: no fake metrics, testimonials, client logos, awards, or years of experience. Project statuses use honest labels (`Concept` / `In Development` / `Internal Product` / `Client Platform`).

## SEO

- Per-page `Metadata` via `buildMetadata()` (`src/lib/seo.ts`): unique title/description, canonical URL, Open Graph + Twitter card.
- JSON-LD via `<JsonLd />` + builders in `src/lib/schema.ts`: `Person`, `Organization`, `WebSite` (global, in `layout.tsx`), plus per-page `ProfilePage`, `Service`, `BreadcrumbList`, `Article`, `FAQPage`, `ContactPage`, `CreativeWork`.
- `src/app/sitemap.ts` and `src/app/robots.ts` (Next.js file-convention, generate real `sitemap.xml` / `robots.txt`).
- `src/app/opengraph-image.tsx` generates a real branded PNG (via `next/og`) as the default social preview image for any page that doesn't set its own.
- All 3D-hero copy (headlines, descriptions, CTAs) is real server-rendered HTML layered over the canvas — nothing meaningful is locked inside WebGL.

## Contact form

The site is a static export with no Node.js server available at runtime, so `src/components/forms/ContactForm.tsx` posts to a **PHP** handler rather than a Next.js API route: `public/contact-handler.php` (copied into `out/` — and therefore your web root — automatically since it lives in `public/`).

- Shared validation logic in `src/lib/contact.ts` is mirrored field-for-field in the PHP script (required fields, email format, message length, consent checkbox) so both stay in sync if you change the rules.
- A hidden honeypot field (`website`) — a filled value is rejected as spam server-side without revealing the honeypot to the client.
- A file-based sliding-window rate limiter (5 requests / 10 minutes per IP), stored under the system temp directory since shared hosting has no Redis/KV available by default.
- Delivery uses PHP's built-in `mail()`, sent to the address in `$recipientEmail` at the top of the script (defaults to `hello@arfaat.com` — **update this**). Before going live, also check the `From:` header comment in the script: many hosts, including IONOS, reject or spam-flag mail sent "from" an address that isn't a real mailbox on your own domain. If plain `mail()` proves unreliable, swap the send step for [PHPMailer](https://github.com/PHPMailer/PHPMailer) over your IONOS SMTP credentials — the script has a comment marking exactly where.

If you ever move to a Node-capable host (Vercel, IONOS Deploy Now, a VPS), you can trivially reintroduce a Next.js API route (`src/app/api/contact/route.ts`) using the same `src/lib/contact.ts` validators, point `CONTACT_ENDPOINT` in `ContactForm.tsx` back at it, and drop `output: "export"` from `next.config.ts`.

## Placeholder assets

`public/textures/`, `public/models/`, and `public/images/projects/` each contain a `README.md` explaining exactly what (if anything) is expected there and how to wire it in. Nothing in the current build depends on external texture or model files — fire, smoke, embers, and the shell's surface detail are all procedural (GLSL noise + a canvas-generated sprite), by design, so the site works with zero binary assets beyond the favicon.

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
