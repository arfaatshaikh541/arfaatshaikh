"use client";
import { useCallback, useEffect, useState } from "react";
import { apiFetch, apiUrl, ApiError } from "@/lib/api";

type Summary = { queues: Record<string, Record<string, number>>; arabic_groups: string[]; notice: string };
type Item = { id: string; key: string; group: string | null; status: string; note: string | null; payload: Record<string, unknown>; reviewed_by: string | null; reviewed_by_name?: string | null; reviewed_at: string | null };
type Page = { queue: string; total: number; page: number; items: Item[] };

const QUEUE_LABEL: Record<string, { en: string; ar: string }> = {
  arabic_ui: { en: "Arabic interface text", ar: "نصوص الواجهة العربية" },
  mosque_name_anomaly: { en: "Mosque name anomalies", ar: "أسماء مساجد تحتاج مراجعة" },
  mosque_colocated: { en: "Co-located, different names", ar: "مواقع متطابقة بأسماء مختلفة" },
  mosque_near_identical: { en: "Near-identical names", ar: "أسماء متقاربة جدًا" },
  mosque_duplicate_candidate: { en: "Duplicate candidates", ar: "احتمالات تكرار" },
};
const STATUS_LABEL: Record<string, string> = {
  OPEN: "Open", KEEP_AS_IS: "Kept as is", NEEDS_SOURCE_CHECK: "Needs source check", CONFIRMED_DUPLICATE: "Confirmed duplicate",
  NEEDS_NATIVE_REVIEW: "Needs native review", NATIVE_REVIEW_APPROVED: "Approved by a native reader", NATIVE_REVIEW_CHANGES_REQUESTED: "Change requested",
};

export function ReviewQueues({ ar }: { ar: boolean }) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [queue, setQueue] = useState("arabic_ui");
  const [group, setGroup] = useState("");
  const [status, setStatus] = useState("NEEDS_NATIVE_REVIEW");
  const [page, setPage] = useState<Page | null>(null);
  const [msg, setMsg] = useState("");
  const [attest, setAttest] = useState<Record<string, boolean>>({});
  const [text, setText] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    try {
      setSummary(await apiFetch<Summary>("/admin/review"));
      const q = new URLSearchParams(); if (group) q.set("group", group); if (status) q.set("status", status);
      setPage(await apiFetch<Page>(`/admin/review/${queue}?${q.toString()}`));
    } catch (e) { setMsg(e instanceof ApiError ? e.message : "Error"); }
  }, [queue, group, status]);
  useEffect(() => { void load(); }, [load]);

  async function sync() {
    try { await apiFetch(`/admin/review/sync/${queue === "arabic_ui" ? "arabic_ui" : "mosques"}`, { method: "POST" }); setMsg(ar ? "حُمّلت العناصر." : "Flagged items loaded."); await load(); }
    catch (e) { setMsg(e instanceof ApiError ? e.message : "Error"); }
  }
  async function decide(item: Item, next: string) {
    setMsg("");
    try {
      await apiFetch(`/admin/review/items/${item.id}/decide`, { method: "POST", body: JSON.stringify({ status: next, suggested_text: text[item.id] || undefined, note: text[item.id] || undefined, attest_native_reader: !!attest[item.id] }) });
      await load();
    } catch (e) { setMsg(e instanceof ApiError ? e.message : "Error"); }
  }

  const counts = summary?.queues[queue] ?? {};
  const isArabic = queue === "arabic_ui";
  return (
    <section aria-label={ar ? "طوابير المراجعة" : "Review queues"} data-testid="review-queues">
      {summary && <p className="tool-note">{summary.notice}</p>}
      <nav className="knowledge-types" aria-label={ar ? "الطابور" : "Queue"}>{Object.keys(QUEUE_LABEL).map((q) => (
        <button key={q} className={queue === q ? "chip chip-active" : "chip"} onClick={() => { setQueue(q); setGroup(""); setStatus(q === "arabic_ui" ? "NEEDS_NATIVE_REVIEW" : ""); }}>
          {QUEUE_LABEL[q][ar ? "ar" : "en"]} ({Object.values(summary?.queues[q] ?? {}).reduce((a, b) => a + b, 0)})</button>))}</nav>
      <p>{Object.entries(counts).map(([k, v]) => `${STATUS_LABEL[k] ?? k}: ${v}`).join(" · ") || (ar ? "لا عناصر محمّلة بعد." : "Nothing loaded yet.")}
        {" "}<button className="chip" onClick={() => void sync()}>{ar ? "تحميل العناصر المُعلَّمة" : "Load flagged items"}</button></p>
      {isArabic && (() => { const total = Object.values(counts).reduce((a, b) => a + b, 0); const done = counts.NATIVE_REVIEW_APPROVED ?? 0; return total ? (
        <p data-testid="review-progress"><progress max={total} value={done} aria-label="progress" /> {done}/{total} {ar ? "معتمدة من قارئ أصلي" : "approved by a native reader"}
          {" "}<a className="chip" href={apiUrl(`/admin/review/arabic_ui/export.csv${status ? `?status=${status}` : ""}`)}>{ar ? "تنزيل CSV للمراجِع" : "Download CSV for a reviewer"}</a></p>) : null; })()}
      {isArabic && <p><label>{ar ? "المجموعة" : "Group"} <select value={group} onChange={(e) => setGroup(e.target.value)}><option value="">{ar ? "الكل" : "All"}</option>{summary?.arabic_groups.map((g) => <option key={g}>{g}</option>)}</select></label>
        {" "}<label>{ar ? "الحالة" : "State"} <select value={status} onChange={(e) => setStatus(e.target.value)}><option value="">{ar ? "الكل" : "All"}</option>{Object.keys(STATUS_LABEL).filter((s) => s.startsWith("NEEDS_NATIVE") || s.startsWith("NATIVE")).map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}</select></label></p>}
      {msg && <p role="status">{msg}</p>}
      <p>{page ? `${page.total}` : "…"} {ar ? "عنصرًا" : "items"}</p>
      <ul className="record-list">{page?.items.map((item) => {
        const p = item.payload;
        return (
          <li key={item.id} className="record-card" data-testid="review-item">
            {isArabic ? (<>
              <p lang="ar" dir="rtl" style={{ fontSize: "1.15rem" }}>{String(p.arabic)}</p>
              <p><small>{ar ? "المصدر الإنجليزي" : "English source"}: {String(p.english ?? "-")} · {ar ? "الفئة" : "Category"}: {item.group} · <code>{String(p.file)}</code></small></p>
              {Boolean(p.context) && <p><small>{ar ? "السياق" : "Context"}: <code dir="ltr">{String(p.context)}</code></small></p>}
              {Boolean(p.religious_term) && <p className="tool-note">{ar ? "يحتوي مصطلحًا شرعيًا: لا يُعاد صوغه إلا على يد مختص." : "Contains religious terminology: only someone qualified should reword it."}</p>}
              <p><span className={item.status === "NATIVE_REVIEW_APPROVED" ? "status-pill status-implemented" : "status-pill status-not-verified"}>{STATUS_LABEL[item.status] ?? item.status}</span>
                {item.reviewed_at && <small> {ar ? "المراجِع" : "Reviewer"}: {item.reviewed_by_name ?? "-"} · {new Date(item.reviewed_at).toLocaleString(ar ? "ar" : "en")}</small>}
                {Boolean(p.suggested_text) && <small> · {ar ? "اقتراح" : "Suggested"}: <span lang="ar" dir="rtl">{String(p.suggested_text)}</span></small>}</p>
              <label><input type="checkbox" checked={!!attest[item.id]} onChange={(e) => setAttest({ ...attest, [item.id]: e.target.checked })} /> {ar ? "أقرّ بأنني أقرأ العربية بوصفها لغتي الأم وراجعت هذا النص" : "I read Arabic natively and have reviewed this text"}</label>
              <p><input aria-label="suggested text or note" value={text[item.id] ?? ""} onChange={(e) => setText({ ...text, [item.id]: e.target.value })} placeholder={ar ? "نص مقترح أو ملاحظة" : "Suggested text or note"} />
                {" "}<button className="chip" onClick={() => void decide(item, "NATIVE_REVIEW_APPROVED")}>{ar ? "اعتماد" : "Approve"}</button>
                {" "}<button className="chip" onClick={() => void decide(item, "NATIVE_REVIEW_CHANGES_REQUESTED")}>{ar ? "طلب تعديل" : "Request change"}</button></p>
            </>) : (<>
              <p><strong>{String(p.a_name ?? p.name ?? "")}</strong>{p.b_name ? <> ↔ <strong>{String(p.b_name)}</strong></> : null} {p.distance_m !== undefined && <small>({String(p.distance_m)} m)</small>}</p>
              <p><small><code>{String(p.a_key ?? p.key ?? "")}</code>{p.b_key ? <> · <code>{String(p.b_key)}</code></> : null}</small></p>
              <p><span className="status-pill status-not-verified">{STATUS_LABEL[item.status] ?? item.status}</span> {item.reviewed_at && <small>{item.reviewed_at}</small>}</p>
              <p><input aria-label="note" value={text[item.id] ?? ""} onChange={(e) => setText({ ...text, [item.id]: e.target.value })} placeholder={ar ? "ملاحظة" : "Note"} />
                {" "}<button className="chip" onClick={() => void decide(item, "KEEP_AS_IS")}>{ar ? "إبقاء كما هو" : "Keep as is"}</button>
                {" "}<button className="chip" onClick={() => void decide(item, "NEEDS_SOURCE_CHECK")}>{ar ? "يحتاج مراجعة المصدر" : "Needs source check"}</button>
                {queue !== "mosque_name_anomaly" && <>{" "}<button className="chip" onClick={() => void decide(item, "CONFIRMED_DUPLICATE")}>{ar ? "تكرار مؤكد" : "Confirmed duplicate"}</button></>}</p>
            </>)}
          </li>);
      })}</ul>
    </section>
  );
}
