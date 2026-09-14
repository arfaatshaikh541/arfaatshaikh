"use client";
import type { Locale } from "@world-of-islam/shared-types";
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { worlds, type Feature, type World } from "@/lib/worlds";

interface Hit { world: World; feature: Feature }

// Strips apostrophes/punctuation so a plain-typed query like "quran" still
// matches a properly transliterated registry entry like "Qur'an".
function fold(value: string): string {
  return value.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, "");
}

export function search(query: string): Hit[] {
  const q = fold(query);
  if (!q) return [];
  const hits: Hit[] = [];
  for (const world of worlds) {
    for (const feature of world.features) {
      if (fold(feature.name).includes(q) || fold(world.name).includes(q) || fold(feature.note).includes(q)) {
        hits.push({ world, feature });
      }
    }
  }
  return hits.slice(0, 20);
}

export function CommandPalette({ locale }: { locale: Locale }) {
  const ar = locale === "ar";
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const hits = useMemo(() => search(query), [query]);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      } else if (e.key === "Escape") {
        setOpen(false);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActiveIndex(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  function go(hit: Hit) {
    setOpen(false);
    const href = hit.feature.status === "available" && hit.feature.href ? hit.feature.href : `/w/${hit.world.slug}`;
    router.push(`/${locale}${href}`);
  }

  function onInputKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") { e.preventDefault(); setActiveIndex((i) => Math.min(i + 1, hits.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActiveIndex((i) => Math.max(i - 1, 0)); }
    else if (e.key === "Enter" && hits[activeIndex]) { go(hits[activeIndex]); }
  }

  return (
    <>
      <button
        type="button"
        className="command-trigger"
        onClick={() => setOpen(true)}
        aria-label={ar ? "بحث في عالم الإسلام" : "Search World of Islam"}
      >
        <span>{ar ? "بحث" : "Search"}</span>
        <kbd>⌘K</kbd>
      </button>
      {open && (
        <div className="command-overlay" onClick={() => setOpen(false)}>
          <div
            className="command-palette"
            role="dialog"
            aria-modal="true"
            aria-label={ar ? "بحث في عالم الإسلام" : "Search World of Islam"}
            onClick={(e) => e.stopPropagation()}
            dir={ar ? "rtl" : "ltr"}
          >
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => { setQuery(e.target.value); setActiveIndex(0); }}
              onKeyDown={onInputKeyDown}
              placeholder={ar ? "ابحث عن القرآن، الحديث، عالم، ميزة…" : "Search Qur'an, Hadith, a scholar, a feature…"}
              aria-label={ar ? "استعلام البحث" : "Search query"}
              aria-activedescendant={hits[activeIndex] ? `cmd-hit-${activeIndex}` : undefined}
              aria-controls="command-results"
              role="combobox"
              aria-expanded={hits.length > 0}
            />
            <ul id="command-results" role="listbox" className="command-results">
              {hits.length === 0 && query.trim() && (
                <li className="command-empty">{ar ? "لا نتائج. جرّب اسم عالم مثل «العبادة» أو «المعرفة»." : "No results. Try a world name like \"Ibadah\" or \"Knowledge\"."}</li>
              )}
              {hits.map((hit, index) => (
                <li
                  key={`${hit.world.slug}-${hit.feature.id}`}
                  id={`cmd-hit-${index}`}
                  role="option"
                  aria-selected={index === activeIndex}
                  className={index === activeIndex ? "command-hit command-hit-active" : "command-hit"}
                  onMouseEnter={() => setActiveIndex(index)}
                  onClick={() => go(hit)}
                >
                  <span className="command-hit-name">{hit.feature.name}</span>
                  <span className="command-hit-world">{ar ? hit.world.nameAr : hit.world.name}</span>
                  <span className={`status-pill status-${hit.feature.status}`}>
                    {hit.feature.status === "available" ? (ar ? "متاح" : "Open") : ar ? "التفاصيل" : "Details"}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </>
  );
}
