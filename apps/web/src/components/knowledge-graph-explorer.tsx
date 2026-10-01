"use client";
import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch, ApiError } from "@/lib/api";

type Rel = { direction: string; type: string; confidence: number; rationale: string; evidence: { passage_key: string; citation: string }; entity: { key: string; type: string; label: string; arabic_label: string; url: string } };
type Entity = { entity: { key: string; type: string; label: string; arabic_label: string; url: string }; relationships: Rel[] };
type Stats = { entities: Record<string, number>; relationships: Record<string, number> };

export function KnowledgeGraphExplorer({ locale }: { locale: "en" | "ar" }) {
  const ar = locale === "ar";
  const [key, setKey] = useState("quran:2:255");
  const [data, setData] = useState<Entity | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [message, setMessage] = useState("");

  async function load(k: string) {
    setMessage(""); setData(null);
    try { setData(await apiFetch<Entity>(`/knowledge/graph/entity?key=${encodeURIComponent(k)}`)); }
    catch (e) { setMessage(e instanceof ApiError && e.status === 404 ? (ar ? "لا يوجد كيان منشور بهذا المفتاح." : "No published entity has that key.") : (ar ? "تعذّر التحميل." : "Could not load.")); }
  }
  useEffect(() => { apiFetch<Stats>("/knowledge/graph/stats").then(setStats).catch(() => undefined); }, []);
  const total = stats ? Object.values(stats.entities).reduce((a, b) => a + b, 0) : 0;
  return (
    <main className="knowledge-page" dir={ar ? "rtl" : "ltr"}>
      <h1>{ar ? "خريطة المعرفة" : "Knowledge graph"}</h1>
      <p className="tool-note">{ar ? "كل علاقة هنا موثقة بمقطع مصدري محدد. لا تُعرض علاقات بلا دليل." : "Every relationship here cites a specific source passage. Relationships without evidence are never shown."}</p>
      {stats && total === 0 && <p role="status">{ar ? "لا توجد كيانات منشورة بعد (تُبنى الخريطة من المصادر المنشورة)." : "No entities are published yet (the graph is built from published sources)."}</p>}
      {stats && total > 0 && <p className="tool-note">{Object.entries(stats.entities).map(([k, v]) => `${k}: ${v}`).join(" · ")} — {Object.entries(stats.relationships).map(([k, v]) => `${k}: ${v}`).join(" · ")}</p>}
      <form onSubmit={(e: FormEvent) => { e.preventDefault(); load(key); }}>
        <label htmlFor="gk">{ar ? "مفتاح الكيان (مثل quran:2:255 أو surah:2)" : "Entity key (e.g. quran:2:255 or surah:2)"}</label>
        <input id="gk" value={key} onChange={(e) => setKey(e.target.value)} dir="ltr" />
        <button>{ar ? "عرض" : "Show"}</button>
      </form>
      {message && <p role="status">{message}</p>}
      {data && (
        <section>
          <h2>{data.entity.label} <small lang="ar">{data.entity.arabic_label}</small></h2>
          <ul className="record-list">
            {data.relationships.map((r, i) => (
              <li key={i} className="record-card">
                <strong>{r.direction === "outgoing" ? "→" : "←"} {r.type}</strong> <button className="linklike" onClick={() => { setKey(r.entity.key); load(r.entity.key); }}>{r.entity.label}</button>
                <p>{r.rationale}</p>
                <small>{ar ? "الدليل" : "Evidence"}: {r.evidence.citation} · {ar ? "الثقة" : "confidence"} {r.confidence}%{" · "}<Link href={`/${locale}${r.entity.url}`}>{ar ? "فتح" : "Open"}</Link></small>
              </li>
            ))}
            {data.relationships.length === 0 && <li>{ar ? "لا علاقات منشورة." : "No published relationships."}</li>}
          </ul>
        </section>
      )}
    </main>
  );
}
