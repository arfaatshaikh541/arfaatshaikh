"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "gridkeep-dir";

function initialDir(): "ltr" | "rtl" {
  if (typeof window === "undefined") return "ltr";
  return window.localStorage.getItem(STORAGE_KEY) === "rtl" ? "rtl" : "ltr";
}

// DirToggle is a layout-mirroring readiness check, not a translation
// feature: flipping dir re-renders every page's logical Tailwind
// properties (text-start, ms-/me-, start-/end-, the .rtl-mirror arrow
// class) mirrored, with the English copy left as-is. It exists so the
// mirrored layout can be exercised and reviewed without first building
// out real Arabic/Hebrew locale strings.
export function DirToggle() {
  const [dir, setDir] = useState<"ltr" | "rtl">(initialDir);

  useEffect(() => {
    document.documentElement.dir = dir;
  }, [dir]);

  const toggle = () => {
    const next = dir === "ltr" ? "rtl" : "ltr";
    setDir(next);
    window.localStorage.setItem(STORAGE_KEY, next);
  };

  return (
    <button
      onClick={toggle}
      aria-label="Toggle layout direction (left-to-right / right-to-left)"
      suppressHydrationWarning
      className="fixed bottom-2 end-2 z-50 rounded-md border border-zinc-300 bg-white px-2 py-1 text-xs text-zinc-600 shadow-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400"
    >
      {dir === "ltr" ? "LTR" : "RTL"}
    </button>
  );
}
