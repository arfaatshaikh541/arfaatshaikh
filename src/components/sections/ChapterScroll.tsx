"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { heroChapters } from "@/data/heroChapters";
import { applyChapterProgress, CHAPTER_STATES } from "@/lib/sceneStore";
import { SphereCanvasLazy } from "@/components/three/SphereCanvasLazy";

if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger);
}

const VH_PER_CHAPTER = 115;

export function ChapterScroll() {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const copyRefs = useRef<(HTMLDivElement | null)[]>([]);
  const scrollCueRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const wrapper = wrapperRef.current;
    if (!wrapper) return;

    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;
    const translateAmount = prefersReducedMotion ? 6 : 32;

    const trigger = ScrollTrigger.create({
      trigger: wrapper,
      start: "top top",
      end: "bottom bottom",
      scrub: 0.6,
      onUpdate: (self) => {
        applyChapterProgress(self.progress, CHAPTER_STATES);

        const scaled = self.progress * (heroChapters.length - 1);

        copyRefs.current.forEach((el, index) => {
          if (!el) return;
          const distance = scaled - index;
          const opacity = Math.max(0, 1 - Math.abs(distance) * 2.2);
          const y = distance * translateAmount;
          el.style.opacity = String(opacity);
          el.style.transform = `translateY(${y}px)`;
          const isReachable = opacity > 0.4;
          el.style.pointerEvents = isReachable ? "auto" : "none";
          const link = el.querySelector("a");
          if (link) {
            if (isReachable) link.removeAttribute("tabindex");
            else link.setAttribute("tabindex", "-1");
          }
        });

        if (scrollCueRef.current) {
          scrollCueRef.current.style.opacity = String(Math.max(0, 1 - scaled * 3));
        }
      },
    });

    return () => trigger.kill();
  }, []);

  return (
    <div
      ref={wrapperRef}
      style={{ height: `${VH_PER_CHAPTER * heroChapters.length}vh` }}
      className="relative"
    >
      <div className="sticky top-0 h-screen w-full overflow-hidden bg-black">
        <div className="absolute inset-0 z-0">
          <SphereCanvasLazy />
        </div>

        <div aria-hidden="true" className="pointer-events-none absolute inset-0 z-[5] bg-gradient-to-t from-black via-transparent to-black/40" />

        <div className="relative z-10 flex h-full w-full flex-col justify-center">
          {heroChapters.map((chapter, index) => (
            <div
              key={chapter.id}
              ref={(el) => {
                copyRefs.current[index] = el;
              }}
              className="container-edge absolute inset-0 flex flex-col justify-center"
              style={{ opacity: index === 0 ? 1 : 0 }}
            >
              <p className="font-mono text-xs uppercase tracking-[0.25em] text-[var(--color-blood-red)] md:text-sm">
                {chapter.eyebrow}
              </p>
              {index === 0 ? (
                <h1 className="text-balance mt-5 max-w-3xl whitespace-pre-line font-display text-5xl uppercase leading-[0.92] text-[var(--color-off-white)] sm:text-6xl md:text-7xl lg:text-8xl">
                  {chapter.title}
                </h1>
              ) : (
                <h2 className="text-balance mt-5 max-w-3xl whitespace-pre-line font-display text-5xl uppercase leading-[0.92] text-[var(--color-off-white)] sm:text-6xl md:text-7xl lg:text-8xl">
                  {chapter.title}
                </h2>
              )}
              <p className="mt-6 max-w-lg text-base leading-relaxed text-[var(--color-muted)] md:text-lg">
                {chapter.description}
              </p>
              {chapter.cta && (
                <Link
                  href={chapter.cta.href}
                  tabIndex={index === 0 ? undefined : -1}
                  className="group mt-8 inline-flex w-fit items-center gap-3 border border-[var(--color-line)] px-6 py-3 font-mono text-xs uppercase tracking-[0.15em] text-[var(--color-off-white)] transition-colors hover:border-[var(--color-blood-red)] hover:text-[var(--color-blood-red)]"
                >
                  {chapter.cta.label}
                  <span aria-hidden="true" className="transition-transform group-hover:translate-x-1">
                    →
                  </span>
                </Link>
              )}
            </div>
          ))}
        </div>

        <div
          ref={scrollCueRef}
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 bottom-8 z-10 flex flex-col items-center gap-2"
        >
          <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-[var(--color-muted)]">
            Scroll
          </span>
          <span className="h-10 w-px animate-pulse bg-[var(--color-blood-red)]" />
        </div>
      </div>
    </div>
  );
}
