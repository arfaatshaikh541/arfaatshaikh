"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Canvas } from "@react-three/fiber";
import PostFX from "./PostFX";
import WebGLFallback from "./WebGLFallback";

function detectWebGL(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return !!(canvas.getContext("webgl2") || canvas.getContext("webgl") || canvas.getContext("experimental-webgl"));
  } catch {
    return false;
  }
}

// Hard cap on simultaneous live WebGL contexts. Mobile Safari and many
// integrated GPUs silently drop the oldest context well before the spec's
// implementation-defined limit, so canvases beyond the budget fall back to
// a static poster instead of fighting for a context.
const MAX_LIVE_CONTEXTS = 9;
let liveContexts = 0;

interface SceneCanvasProps {
  children: React.ReactNode;
  camera?: { position: [number, number, number]; fov?: number };
  postFX?: boolean;
  strongBloom?: boolean;
  className?: string;
  posterLabel?: string;
  eager?: boolean;
}

export default function SceneCanvas({
  children,
  camera = { position: [0, 0, 6], fov: 42 },
  postFX = true,
  strongBloom = false,
  className = "",
  posterLabel = "GRIDKEEP",
  eager = false,
}: SceneCanvasProps) {
  const [supported, setSupported] = useState<boolean | null>(null);
  const [inView, setInView] = useState(eager);
  const [tabActive, setTabActive] = useState(true);
  const [reduced, setReduced] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const reservedRef = useRef(false);
  const [timedOut, setTimedOut] = useState(false);
  const [contextLost, setContextLost] = useState(false);

  useEffect(() => {
    setSupported(detectWebGL());
    setReduced(window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    setIsMobile(window.matchMedia("(max-width: 768px)").matches);

    const onVisibility = () => setTabActive(!document.hidden);
    document.addEventListener("visibilitychange", onVisibility);

    const timeout = window.setTimeout(() => setTimedOut(true), 8000);

    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      window.clearTimeout(timeout);
    };
  }, []);

  useEffect(() => {
    // Even "eager" canvases (mounted immediately on load, e.g. the hero) still
    // release their context once scrolled well out of view, so the fixed
    // budget favors whatever is actually on screen.
    if (!containerRef.current) return;
    const el = containerRef.current;
    const observer = new IntersectionObserver(([entry]) => setInView(entry.isIntersecting), {
      rootMargin: "150px",
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const shouldMount = supported === true && inView && !timedOut;

  // Reservation happens synchronously during render (not in an effect) so the
  // context budget is settled for every SceneCanvas in the tree before any of
  // them mount an actual <Canvas> and create a real WebGL context.
  const hasBudget = useMemo(() => {
    if (!shouldMount) {
      if (reservedRef.current) {
        liveContexts -= 1;
        reservedRef.current = false;
      }
      return false;
    }
    if (reservedRef.current) return true;
    if (liveContexts >= MAX_LIVE_CONTEXTS) return false;
    liveContexts += 1;
    reservedRef.current = true;
    return true;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shouldMount]);

  useEffect(() => {
    return () => {
      if (reservedRef.current) {
        liveContexts -= 1;
        reservedRef.current = false;
      }
    };
  }, []);

  if (supported === false || timedOut || contextLost) {
    return (
      <div ref={containerRef} className={`gk-canvas-wrap ${className}`} aria-hidden="true">
        <WebGLFallback label={posterLabel} />
      </div>
    );
  }

  return (
    <div ref={containerRef} className={`gk-canvas-wrap ${className}`} aria-hidden="true">
      {shouldMount && hasBudget ? (
        <Canvas
          dpr={isMobile ? [1, 1.2] : [1, 1.8]}
          gl={{ antialias: false, powerPreference: "high-performance", alpha: true }}
          camera={camera}
          frameloop={tabActive ? "always" : "never"}
          onCreated={({ gl }) => {
            gl.setClearColor(0x000000, 0);
            gl.domElement.addEventListener(
              "webglcontextlost",
              (e) => {
                e.preventDefault();
                setContextLost(true);
              },
              { once: true }
            );
          }}
        >
          <Suspense fallback={null}>
            {children}
            {postFX && !reduced && !isMobile && <PostFX strong={strongBloom} />}
          </Suspense>
        </Canvas>
      ) : (
        <div className="h-full w-full animate-pulse-glow bg-gradient-to-br from-black-surface via-black-near to-black" />
      )}
    </div>
  );
}
