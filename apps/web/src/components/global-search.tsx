"use client";
import Link from "next/link";
import { useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import { SEARCH_TYPES } from "@/lib/copy";

type Result = { type: string; title: string; snippet: string; reference: string; source: string; license: string | null; path: string; language?: string; layer?: string; verification_status?: string; scholarly_status?: string };
type Response = { query: string; results: Result[]; empty_types: string[]; searched_types: string[] };

const LAYER: Record<string, { en: string; ar: string }> = {
  primary_source: { en: "Primary source", ar: "مصدر أصلي" },
  scholarly_explanation: { en: "Scholarly explanation", ar: "شرح علمي" },
  secondary_source: { en: "Secondary source", ar: "مصدر ثانوي" },
};

export function GlobalSearch({ locale }: { locale: "en" | "ar" }) {
  const ar = locale === "ar";
  const [query, setQuery] = useState("");
  const [types, setTypes] = useState<string[]>([]);
  const [data, setData] = useState<Response | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (query.trim().length < 2) return;
    setBusy(true); setError(""); setData(null);
    try {
      const params = new URLSearchParams({ q: query.trim() });
      if (types.length) params.set("types", types.join(","));
      setData(await apiFetch<Response>(`/search?${params}`));
    } catch (err) {
      setError(err instanceof ApiError && err.status === 429 ? (ar ? "طلبات كثيرة. حاول بعد قليل." : "Too many searches. Try again shortly.") : ar ? "تعذّر إتمام البحث." : "Search could not be completed.");
    } finally { setBusy(false); }
  }
  const label = (id: string) => SEARCH_TYPES.find((t) => t.id === id)?.[ar ? "ar" : "en"] ?? id;
  return (
    <div className="global-search" dir={ar ? "rtl" : "ltr"}>
      <form onSubmit={submit} className="global-search-form" role="search">
        <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} minLength={2} required aria-label={ar ? "استعلام البحث" : "Search query"}
          placeholder={ar ? "ابحث في المصادر المنشورة…" : "Search published sources…"} />
        <div className="knowledge-types" role="group" aria-label={ar ? "أنواع المحتوى" : "Content types"}>
          {SEARCH_TYPES.map((t) => <button type="button" key={t.id} aria-pressed={types.includes(t.id)} className={types.includes(t.id) ? "chip chip-active" : "chip"}
            onClick={() => setTypes((prev) => prev.includes(t.id) ? prev.filter((x) => x !== t.id) : [...prev, t.id])}>{ar ? t.ar : t.en}</button>)}
        </div>
        <p className="tool-note">{types.length === 0 ? (ar ? "يُبحث في كل الأنواع." : "Searching every type.") : (ar ? "يُبحث في الأنواع المختارة فقط." : "Searching the selected types only.")}</p>
        <button type="submit" disabled={busy || query.trim().length < 2}>{busy ? (ar ? "جارٍ البحث…" : "Searching…") : ar ? "بحث" : "Search"}</button>
      </form>
      {error && <p role="alert" className="global-search-error">{error}</p>}
      {data && (
        <section aria-live="polite" className="global-search-results">
          {data.results.length === 0 ? (
            <p className="tool-note">{ar ? "لا نتائج في المصادر المنشورة. لا تُعرض نتائج غير موثقة." : "No results in the published sources. Unverified results are never shown."}</p>
          ) : (
            <ul className="record-list">
              {data.results.map((r, i) => (
                <li key={i} className="record-card">
                  <p><span className="status-pill status-implemented">{label(r.type)}</span>{r.layer && <> <span className="status-pill status-architecture-ready">{LAYER[r.layer]?.[ar ? "ar" : "en"]}</span></>}</p>
                  <h2><Link href={`/${locale}${r.path}`}>{r.title}</Link></h2>
                  <p lang={r.language === "ar" ? "ar" : undefined} dir={r.language === "ar" ? "rtl" : undefined} className={r.language === "ar" ? "arabic-text" : undefined}>{r.snippet}</p>
                  <small>{r.source}{r.license ? ` · ${r.license}` : ""}</small>
                </li>
              ))}
            </ul>
          )}
          {data.empty_types.length > 0 && <p className="tool-note">{ar ? "لا بيانات منشورة حالياً في: " : "No published data currently in: "}{data.empty_types.map(label).join(", ")}.</p>}
        </section>
      )}
    </div>
  );
}
