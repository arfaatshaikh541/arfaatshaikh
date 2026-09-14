"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

type Grading = { grader_name: string; grading_label: string; grading_text: string; methodology_note?: string | null };
type Translation = { translation_key: string; translator_name: string; attribution_text: string; translated_text: string };
type IsnadNode = { position: number; narrator_id?: string | null; transmitted_name: string; transmission_term?: string | null };
type Narration = { id: string; canonical_reference: string; collection_hadith_number: number; arabic_matn: string; translations: Translation[]; gradings: Grading[] };
type Chapter = { collection_key: string; collection_title: string; book_number: number; book_title: string; chapter_number: number; chapter_title: string; narrations: Narration[] };

export function HadithReader({ locale, collection, book, chapter }: { locale: string; collection: string; book: number; chapter: number }) {
  const [data, setData] = useState<Chapter | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isnad, setIsnad] = useState<Record<string, IsnadNode[]>>({});
  const [status, setStatus] = useState("");

  useEffect(() => {
    apiFetch<Chapter>(`/hadith/collections/${encodeURIComponent(collection)}/books/${book}/chapters/${chapter}`)
      .then(setData).catch((e: Error) => setError(e.message));
  }, [collection, book, chapter]);

  if (error) return <main className="content-shell"><p role="alert">{error}</p></main>;
  if (!data) return <main className="content-shell"><p role="status">{locale === "ar" ? "جارٍ تحميل الباب…" : "Loading chapter…"}</p></main>;

  return <main className="content-shell hadith-reader">
    <header>
      <p>{data.collection_title} · {data.book_title}</p>
      <h1>{data.chapter_title}</h1>
      <p>{locale === "ar" ? "تُعرض أحكام العلماء منفصلة ومنسوبة إلى أصحابها." : "Scholarly grading opinions are shown separately and attributed to their authors."}</p>
    </header>
    {data.narrations.map((n) => <article id={`hadith-${n.collection_hadith_number}`} key={n.id} tabIndex={-1}>
      <a href={`#hadith-${n.collection_hadith_number}`} aria-label={`Hadith ${n.canonical_reference}`}>{n.canonical_reference}</a>
      <p dir="rtl" lang="ar" className="arabic-text">{n.arabic_matn}</p>
      {n.translations.map((t) => <section key={t.translation_key} aria-label="Translation">
        <p>{t.translated_text}</p><small>{t.translator_name} · {t.attribution_text}</small>
      </section>)}
      {n.gradings.length > 0 && <section aria-label="Scholarly grading opinions">
        <h2>{locale === "ar" ? "أحكام العلماء" : "Scholarly grading opinions"}</h2>
        <ul>{n.gradings.map((g, i) => <li key={`${g.grader_name}-${i}`}><strong>{g.grader_name}: {g.grading_label}</strong><p>{g.grading_text}</p>{g.methodology_note && <small>{g.methodology_note}</small>}</li>)}</ul>
      </section>}
      {isnad[n.id] && <section aria-label={locale === "ar" ? "سلسلة الإسناد" : "Narrator chain"}>
        <h2>{locale === "ar" ? "سلسلة الإسناد" : "Narrator chain"}</h2>
        <ol>{isnad[n.id].map((node) => <li key={node.position}>{node.transmission_term ? `${node.transmission_term} ` : ""}{node.transmitted_name}</li>)}</ol>
      </section>}
      <div className="reader-actions">
        <button type="button" onClick={async () => {
          const nodes = await apiFetch<IsnadNode[]>(`/hadith/narrations/${n.id}/isnad`);
          setIsnad((current) => ({ ...current, [n.id]: nodes }));
        }}>{locale === "ar" ? "عرض الإسناد" : "Show isnād"}</button>
        <button type="button" onClick={async () => {
          await navigator.clipboard.writeText(`${n.arabic_matn}\n\n${n.canonical_reference}\n${location.origin}/${locale}/hadith/${collection}/${book}/${chapter}#hadith-${n.collection_hadith_number}`);
          setStatus(locale === "ar" ? "تم نسخ الحديث مع المرجع" : "Hadith copied with citation");
        }}>{locale === "ar" ? "نسخ مع المرجع" : "Copy with citation"}</button>
        <button type="button" onClick={async () => {
          await apiFetch(`/hadith/me/bookmarks`, { method: "POST", body: JSON.stringify({ narration_id: n.id }) });
          setStatus(locale === "ar" ? "تم حفظ العلامة" : "Bookmark saved");
        }}>{locale === "ar" ? "حفظ علامة" : "Bookmark"}</button>
      </div>
    </article>)}
    <p role="status" aria-live="polite">{status}</p>
  </main>;
}
