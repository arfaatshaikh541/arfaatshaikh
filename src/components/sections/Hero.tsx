import Link from "next/link";
import { SphereCanvasLazy } from "@/components/three/SphereCanvasLazy";

// A static hero — no ScrollTrigger pin, no chapter-driven narrative. The 3D
// object still idles/breathes and reacts to hover, click, and gyroscope
// (see SphereRig/CameraRig), just no longer choreographed to scroll
// position. Real text server-rendered in normal document flow, not layered
// over a full-viewport canvas, so the page has one concrete DOM height and
// nothing shifts the H1 as WebGL boots.
export function Hero() {
  return (
    <section className="relative overflow-hidden border-b border-[var(--color-line)] bg-black">
      <div className="container-edge grid gap-12 py-32 pt-36 lg:grid-cols-2 lg:items-center lg:gap-8 lg:py-40 lg:pt-40">
        <div className="relative z-10">
          <p className="font-mono text-xs uppercase tracking-[0.25em] text-[var(--color-blood-red)] md:text-sm">
            Arfaat Shaikh · Creative Engineer
          </p>
          <h1 className="text-balance mt-5 max-w-xl font-display text-5xl uppercase leading-[0.92] text-[var(--color-off-white)] sm:text-6xl md:text-7xl">
            Something is
            <br />
            built to wake.
          </h1>
          <p className="mt-6 max-w-lg text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
            Based in the United Arab Emirates. Founder of GRIDKEEP. I build
            AI agents, automation, custom software, cybersecurity, and cloud
            infrastructure for businesses that need it built properly.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-4">
            <Link
              href="/projects"
              className="group inline-flex w-fit items-center gap-3 border border-[var(--color-blood-red)] bg-[var(--color-blood-red)] px-6 py-3 font-mono text-xs uppercase tracking-[0.15em] text-black transition-colors hover:bg-transparent hover:text-[var(--color-blood-red)]"
            >
              Explore my work
              <span aria-hidden="true" className="transition-transform group-hover:translate-x-1">
                →
              </span>
            </Link>
            <Link
              href="/contact"
              className="group inline-flex w-fit items-center gap-3 border border-[var(--color-line)] px-6 py-3 font-mono text-xs uppercase tracking-[0.15em] text-[var(--color-off-white)] transition-colors hover:border-[var(--color-blood-red)] hover:text-[var(--color-blood-red)]"
            >
              Let&apos;s connect
              <span aria-hidden="true" className="transition-transform group-hover:translate-x-1">
                →
              </span>
            </Link>
          </div>
        </div>

        <div className="relative h-[420px] sm:h-[520px] lg:h-[600px]">
          <SphereCanvasLazy />
        </div>
      </div>
    </section>
  );
}
