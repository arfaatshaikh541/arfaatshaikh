# GRIDKEEP

Founder-led technology systems website — Next.js App Router, TypeScript, React Three Fiber, GSAP, and Lenis.

## Getting Started

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

```bash
npm run build   # production build + static generation
npm run start   # serve the production build
npm run lint    # eslint
```

## Architecture Notes

- **One shared WebGL context.** Browsers cap live WebGL contexts (as low as 8 on mobile
  Safari), and this site has 20+ 3D prototype scenes on the homepage alone. `SceneRoot`
  (`src/components/three/SceneRoot.tsx`) mounts a single, viewport-fixed `<Canvas>` once in the
  root layout. Every `<CanvasStage>` instance tunnels a scissor-rendered `@react-three/drei`
  `<View>` into that shared canvas instead of creating its own context.
- **Procedural 3D, not baked assets.** Every prototype (`src/components/three/prototypes/`) is
  built from primitive geometry, instanced bolts/vents, and PBR materials (`materials.ts`) rather
  than imported GLB files — there's no asset pipeline for hand-modeled/textured meshes in this
  environment. Realism comes from layered hard-surface composition, lighting, and motion.
- **Scroll-driven mechanics.** `useScrollProgress` (`src/hooks/`) ties a GSAP `ScrollTrigger` to a
  mutable ref (not React state), so prototypes read scroll progress inside `useFrame` without
  triggering React re-renders.
- **Data-driven content.** Services, projects, and insights content lives in `src/lib/*-data.ts`.
  Service detail pages, the services grid, and the ecosystem section all read from the same
  source of truth.

## Known follow-ups

- The contact form posts to `/api/contact`, which validates and logs the submission
  server-side. Wiring it to an email/CRM provider (Resend, SendGrid, HubSpot, etc.) is the
  remaining step to deliver intake emails to `hello@gridkeep.com` automatically.
