import { useEffect, useState } from "react";

export function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(query.matches);
    const listener = (event: MediaQueryListEvent) => setReduced(event.matches);
    query.addEventListener("change", listener);
    return () => query.removeEventListener("change", listener);
  }, []);

  return reduced;
}

export function useIsMobile() {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const query = window.matchMedia("(max-width: 768px)");
    setIsMobile(query.matches);
    const listener = (event: MediaQueryListEvent) => setIsMobile(event.matches);
    query.addEventListener("change", listener);
    return () => query.removeEventListener("change", listener);
  }, []);

  return isMobile;
}

export function useDocumentVisible() {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const listener = () => setVisible(document.visibilityState === "visible");
    document.addEventListener("visibilitychange", listener);
    return () => document.removeEventListener("visibilitychange", listener);
  }, []);

  return visible;
}

export function particleCount(base: number, isMobile: boolean, reducedMotion: boolean) {
  if (reducedMotion) return Math.round(base * 0.25);
  if (isMobile) return Math.round(base * 0.4);
  return base;
}
