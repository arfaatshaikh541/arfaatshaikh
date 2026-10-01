"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { KNOWLEDGE_EMPTY, KNOWLEDGE_TYPES, NOT_PUBLIC, READINESS_LABEL } from "@/lib/copy";

type Rec = { id: string; dataset: string; type: string; title: string; arabic_title: string | null; description: string; source: string; source_url: string | null; author: string | null; date: string | null; license: string; provenance: string; scholarly_status: string; confidence: number; last_verified: string | null; tags: string[];
  source_work: string | null; edition: string | null; volume: string | null; page: string | null; chapter: string | null; language: string | null;
  publication_status: string; license_status: string; provenance_status: string; attributes: Attributes };
type Evidence = { type: string; reference?: string; text?: string };
type Grade = { grader: string; grade: string; grading_source: string; note?: string };
type Attributes = { madhhab?: string; school?: string; topic?: string; question?: string; ruling?: string; statement?: string; reasoning?: string; evidence?: Evidence[]; grades?: Grade[];
  collection?: string; hadith_number?: number | string; reliability?: string; availability?: string; external_url?: string; historical_context?: string; [key: string]: unknown };
type Page = { total: number; page: number; page_size: number; items: Rec[] };
type Readiness = { datasets: { id: string; name: string; type: string; public: boolean; readiness: string; record_count: number }[] };

export function KnowledgeBrowser({ locale, type }: { locale: "en" | "ar"; type: string }) {
  const ar = locale === "ar";
  const label = KNOWLEDGE_TYPES.find((t) => t.id === type);
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [position, setPosition] = useState("");
  const [data, setData] = useState<Page | null>(null);
  const [readiness, setReadiness] = useState<Readiness["datasets"]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    const params = new URLSearchParams({ type, page: String(page) });
    if (q.trim()) params.set("q", q.trim());
    if (position.trim()) params.set(type === "aqeedah" ? "school" : "madhhab", position.trim());
    apiFetch<Page>(`/knowledge/records?${params}`).then(setData).catch(() => setError(ar ? "تعذّر تحميل البيانات." : "Could not load the records."));
  }, [type, q, page, position, ar]);
  useEffect(() => { apiFetch<Readiness>(`/knowledge/readiness?entity_type=${type}`).then((r) => setReadiness(r.datasets)).catch(() => undefined); }, [type]);

  const state = readiness[0]?.readiness;
  return (
    <main className="knowledge-page" dir={ar ? "rtl" : "ltr"}>
      <nav className="knowledge-types" aria-label={ar ? "أنواع المعرفة" : "Knowledge types"}>
        {KNOWLEDGE_TYPES.map((t) => <Link key={t.id} href={`/${locale}/knowledge/${t.id}`} aria-current={t.id === type ? "page" : undefined} className={t.id === type ? "chip chip-active" : "chip"}>{ar ? t.ar : t.en}</Link>)}
      </nav>
      <h1>{ar ? label?.ar : label?.en}</h1>
      <form role="search" onSubmit={(e) => { e.preventDefault(); setPage(1); }}>
        <label htmlFor="kq" className="sr-only">{ar ? "بحث" : "Search"}</label>
        <input id="kq" type="search" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} placeholder={ar ? "ابحث في السجلات المنشورة" : "Search published records"} />
      </form>
      {(type === "fiqh" || type === "aqeedah") && (
        <label>{type === "aqeedah" ? (ar ? "المدرسة" : "School") : (ar ? "المذهب" : "Madhhab")}
          <input value={position} onChange={(e) => { setPosition(e.target.value); setPage(1); }} />
        </label>
      )}
      {error && <p role="alert">{error}</p>}
      {data && data.total === 0 && !error && (
        <section className="empty-state" role="status">
          <h2>{(readiness[0]?.record_count ?? 0) > 0 ? NOT_PUBLIC[ar ? "ar" : "en"] : KNOWLEDGE_EMPTY[type]?.[ar ? "ar" : "en"] ?? NOT_PUBLIC[ar ? "ar" : "en"]}</h2>
          <p>{state ? READINESS_LABEL[state]?.[ar ? "ar" : "en"] : ar ? "لم يُحمَّل أي مصدر بعد." : "No source has been loaded yet."}</p>
          <p className="tool-note">{ar ? "لا يعرض هذا القسم إلا مصادر موثقة ومرخّصة، ولا يُولَّد أي محتوى ديني بدلاً منها." : "This section only shows verified, licensed sources. No religious content is generated in their place."}</p>
        </section>
      )}
      <ul className="record-list">
        {data?.items.map((r) => (
          <li key={`${r.dataset}/${r.id}`} className="record-card">
            <h2>{r.title}{r.arabic_title && <span lang="ar" dir="rtl" className="record-ar"> {r.arabic_title}</span>}</h2>
            <p>{r.description}</p>
            <RecordDetail r={r} ar={ar} />
            <dl className="provenance">
              {r.source_work && <div><dt>{ar ? "العمل" : "Work"}</dt><dd>{[r.source_work, r.edition, r.volume && `${ar ? "مج" : "vol."} ${r.volume}`, r.chapter, r.page && `${ar ? "ص" : "p."} ${r.page}`].filter(Boolean).join(" · ")}</dd></div>}
              {r.language && <div><dt>{ar ? "اللغة" : "Language"}</dt><dd>{r.language}</dd></div>}
              <div><dt>{ar ? "المصدر" : "Source"}</dt><dd>{r.source_url ? <a href={r.source_url} rel="noopener noreferrer nofollow">{r.source}</a> : r.source}</dd></div>
              {r.author && <div><dt>{ar ? "المؤلف" : "Author"}</dt><dd>{r.author}</dd></div>}
              {r.date && <div><dt>{ar ? "التاريخ" : "Date"}</dt><dd>{r.date}</dd></div>}
              <div><dt>{ar ? "الترخيص" : "Licence"}</dt><dd>{r.license}</dd></div>
              <div><dt>{ar ? "المنشأ" : "Provenance"}</dt><dd>{r.provenance}</dd></div>
              <div><dt>{ar ? "الحالة العلمية" : "Scholarly status"}</dt><dd>{r.scholarly_status}{r.last_verified ? ` · ${r.last_verified}` : ""}</dd></div>
            </dl>
          </li>
        ))}
      </ul>
      {data && data.total > data.page_size && (
        <div className="pager">
          <button disabled={page <= 1} onClick={() => setPage(page - 1)}>{ar ? "السابق" : "Previous"}</button>
          <span>{page} / {Math.ceil(data.total / data.page_size)}</span>
          <button disabled={page * data.page_size >= data.total} onClick={() => setPage(page + 1)}>{ar ? "التالي" : "Next"}</button>
        </div>
      )}
    </main>
  );
}


/** Type-specific structure. Different scholars' positions or grades are shown side by side and never merged or ranked. */
function RecordDetail({ r, ar }: { r: Rec; ar: boolean }) {
  const a = r.attributes ?? {};
  return (
    <>
      {(a.madhhab || a.school) && <p><strong>{a.madhhab ? (ar ? "المذهب" : "Madhhab") : (ar ? "المدرسة" : "School")}:</strong> {a.madhhab ?? a.school}{a.topic ? ` · ${a.topic}` : ""}</p>}
      {a.question && <p><strong>{ar ? "المسألة" : "Question"}:</strong> {a.question}</p>}
      {a.ruling && <p><strong>{ar ? "الحكم" : "Ruling"}:</strong> {a.ruling}</p>}
      {a.statement && <p><strong>{ar ? "القول" : "Statement"}:</strong> {a.statement}</p>}
      {a.reasoning && <p><strong>{ar ? "التعليل" : "Reasoning"}:</strong> {a.reasoning}</p>}
      {a.evidence && a.evidence.length > 0 && <ul>{a.evidence.map((e, i) => <li key={i}>{e.type}: {e.reference ?? e.text}</li>)}</ul>}
      {a.reliability && <p><strong>{ar ? "درجة الثبوت" : "Reliability of the report"}:</strong> {a.reliability.replace(/_/g, " ")}</p>}
      {a.grades && a.grades.length > 0 && (
        <table className="grades">
          <caption>{ar ? "درجات الحكم على الحديث، لكل حاكم على حدة" : "Gradings, one row per grader (graders are not combined)"}</caption>
          <thead><tr><th scope="col">{ar ? "الحاكم" : "Grader"}</th><th scope="col">{ar ? "الدرجة" : "Grade"}</th><th scope="col">{ar ? "مصدر الحكم" : "Grading source"}</th></tr></thead>
          <tbody>{a.grades.map((g) => <tr key={g.grader}><td>{g.grader}</td><td>{g.grade}</td><td>{g.grading_source}</td></tr>)}</tbody>
        </table>
      )}
      {a.external_url && <p><a href={String(a.external_url)} rel="noopener noreferrer nofollow">{ar ? "المصدر الخارجي" : "External resource"}</a></p>}
    </>
  );
}
