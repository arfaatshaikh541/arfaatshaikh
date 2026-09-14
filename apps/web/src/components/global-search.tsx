"use client";
import { useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";

type Evidence = {
  chunk_id: string;
  corpus_type: string;
  canonical_reference: string;
  exact_text: string;
  attribution: string;
  licence: string;
};
type RetrievalResponse = { policy_version: string; insufficient: boolean; evidence: Evidence[] };

const CORPORA = ["quran", "hadith", "tafsir"] as const;

export function GlobalSearch({ locale }: { locale: "en" | "ar" }) {
  const ar = locale === "ar";
  const [query, setQuery] = useState("");
  const [corpora, setCorpora] = useState<string[]>([...CORPORA]);
  const [results, setResults] = useState<Evidence[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function toggleCorpus(corpus: string) {
    setCorpora((prev) => (prev.includes(corpus) ? prev.filter((c) => c !== corpus) : [...prev, corpus]));
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!query.trim() || corpora.length === 0) return;
    setBusy(true);
    setError("");
    setResults(null);
    try {
      const response = await apiFetch<RetrievalResponse>("/retrieval/query", {
        method: "POST",
        body: JSON.stringify({ query, language: locale, corpora, limit: 20 }),
      });
      setResults(response.evidence);
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 401
          ? ar ? "سجّل الدخول للبحث في عالم الإسلام." : "Sign in to search World of Islam."
          : ar ? "تعذّر إتمام البحث." : "Search could not be completed.",
      );
    } finally {
      setBusy(false);
    }
  }

  const corpusLabel: Record<string, { en: string; ar: string }> = {
    quran: { en: "Qur'an", ar: "القرآن" },
    hadith: { en: "Hadith", ar: "الحديث" },
    tafsir: { en: "Tafsir", ar: "التفسير" },
  };

  return (
    <div className="global-search">
      <form onSubmit={submit} className="global-search-form">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={ar ? "ابحث في القرآن والحديث والتفسير المعتمد…" : "Search approved Qur'an, Hadith, and Tafsir text…"}
          aria-label={ar ? "استعلام البحث" : "Search query"}
          minLength={2}
          required
        />
        <div className="global-search-corpora" role="group" aria-label={ar ? "المصادر" : "Corpora"}>
          {CORPORA.map((c) => (
            <label key={c} className="corpus-toggle">
              <input type="checkbox" checked={corpora.includes(c)} onChange={() => toggleCorpus(c)} />
              {ar ? corpusLabel[c].ar : corpusLabel[c].en}
            </label>
          ))}
        </div>
        <button type="submit" disabled={busy || !query.trim() || corpora.length === 0}>
          {busy ? (ar ? "جارٍ البحث…" : "Searching…") : ar ? "بحث" : "Search"}
        </button>
      </form>

      {error && <p role="alert" className="global-search-error">{error}</p>}

      {results !== null && (
        <section aria-live="polite" className="global-search-results">
          {results.length === 0 ? (
            <p className="tool-note">
              {ar
                ? "لا توجد أدلة معتمدة مطابقة. هذا يعني عدم وجود نص منشور ومعتمد يطابق بحثك - وليس تخمينًا."
                : "No approved evidence matches. This means no published, approved text matches your search — not a guess."}
            </p>
          ) : (
            <ul className="global-search-list">
              {results.map((item) => (
                <li key={item.chunk_id} className="global-search-item">
                  <span className={`status-pill status-available`}>{corpusLabel[item.corpus_type]?.[ar ? "ar" : "en"] ?? item.corpus_type}</span>
                  <p className="global-search-reference">{item.canonical_reference}</p>
                  <p className={item.corpus_type === "quran" || item.corpus_type === "hadith" || item.corpus_type === "tafsir" ? "arabic-text" : undefined} lang={ar ? undefined : "ar"} dir="rtl">
                    {item.exact_text}
                  </p>
                  <small>{item.attribution} · {item.licence}</small>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
