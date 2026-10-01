"use client";

import { FormEvent, useState } from "react";
import { apiFetch } from "@/lib/api";
import { AUTHORITY_LABEL, INSUFFICIENT } from "@/lib/copy";

type Item = { label: string; reference: string; attribution: string; text: string; license: string; relevance: number; authority_class?: string; verification_state?: string };
type Sections = { primary_source: Item[]; scholarly_explanation: Item[]; secondary_source: Item[] };
type KnowledgeSource = { authority_class: string; verification_state: string; source_title: string; author: string | null; edition: string | null; url: string | null; record: { dataset: string; id: string }; label: string; kind: string; title: string; text: string; position: string | null; source: string; source_work: string | null; locator: string; license: string; scholarly_status: string; uncertainty: string[] };
type Answer = {
  knowledge_sources?: KnowledgeSource[];
  status: string; message?: string; insufficiency_reason?: string | null; requires_escalation?: boolean; response_text?: string | null;
  sections?: Sections; confidence?: { score: number; level: string; abstained: boolean; reasons: string[] };
  scholarly_views?: { reference: string; views: { attribution: string }[]; note: string }[];
  ai_synthesis?: { status: string; text: string | null; notice?: string; reasons?: string[] };
};

export function IslamicAssistant({ locale }: { locale: "en" | "ar" }) {
  const rtl = locale === "ar";
  const [question, setQuestion] = useState("");
  const [synthesis, setSynthesis] = useState(false);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [busy, setBusy] = useState(false);

  const copy = rtl ? {
    title: "المساعد الإسلامي الموثّق", intro: "إجابات مبنية على مصادر منشورة ومعتمدة فقط. تُعرض النصوص حرفياً مع مصدرها، وإن لم تكفِ المصادر فلا إجابة.",
    placeholder: "اكتب سؤالك…", submit: "بحث وإجابة", sources: "المصادر",
    primary: "مصدر أصلي", scholarly: "شرح علمي", secondary: "مصدر ثانوي", ai: "توليف الذكاء الاصطناعي",
    synthLabel: "أضف ملخصاً بالذكاء الاصطناعي (نموذج محلي، يُعرض فقط إن اجتاز التحقق من الاستشهادات)",
    aiNotice: "كتبه نموذج لغوي من المصادر أعلاه. ليس مصدراً بحد ذاته.", aiUnavailable: "الملخص غير متاح: لا يوجد نموذج محلي يعمل.", aiRejected: "رُفض الملخص لأنه لم يجتز التحقق من الاستشهادات.",
    confidence: "مستوى الثقة", views: "عدة علماء يعلّقون على", boundary: "هذه معلومات عامة قائمة على المصادر وليست فتوى شخصية.",
  } : {
    title: "Evidence-grounded Islamic assistant", intro: "Answers come only from published, approved sources. Texts are quoted verbatim with their source; if the sources are not enough, there is no answer.",
    placeholder: "Ask an Islamic question…", submit: "Find grounded answer", sources: "Sources",
    primary: "Primary source", scholarly: "Scholarly explanation", secondary: "Secondary source", ai: "AI synthesis",
    synthLabel: "Add an AI summary (local model; shown only if every citation validates)",
    aiNotice: "Written by a language model from the sources above. It is not itself a source.", aiUnavailable: "Summary unavailable: no local model is running.", aiRejected: "The summary was rejected because it failed citation validation.",
    confidence: "Confidence", views: "Several scholars comment on", boundary: "This is general, source-based information, not a personal fatwa.",
  };

  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setAnswer(null);
    try { setAnswer(await apiFetch<Answer>("/assistant/query", { method: "POST", body: JSON.stringify({ question, locale, include_synthesis: synthesis }) })); }
    catch { setAnswer({ status: "insufficient", insufficiency_reason: "request_failed" }); }
    finally { setBusy(false); }
  }
  const section = (key: keyof Sections, title: string, cls: string) => {
    const items = answer?.sections?.[key] ?? [];
    if (!items.length) return null;
    return (
      <section className={`answer-section ${cls}`} aria-label={title}>
        <h3>{title}</h3>
        {items.map((item) => (
          <article key={item.label}>
            <p><strong>{item.label}</strong> {item.reference} · {item.attribution}</p>
            <blockquote lang={/[؀-ۿ]/.test(item.text) ? "ar" : undefined} dir={/[؀-ۿ]/.test(item.text) ? "rtl" : undefined}>{item.text}</blockquote>
            <small>{item.license}</small>
            {item.authority_class && <p className="tool-note"><span className="status-pill status-implemented">{AUTHORITY_LABEL[item.authority_class]?.[rtl ? "ar" : "en"]}</span> <small>{item.verification_state}</small></p>}
          </article>
        ))}
      </section>
    );
  };


  const knowledge = (answer?.knowledge_sources ?? []).length > 0 && (
    <section className="answer-section" aria-label={rtl ? "سجلات موثّقة ذات صلة" : "Related sourced records"}>
      <h3>{rtl ? "سجلات موثّقة ذات صلة" : "Related sourced records"}</h3>
      <p className="tool-note">{rtl ? "تُعرض المواقف العلمية المختلفة منفصلة، دون دمج أو ترجيح." : "Different scholarly positions are listed separately; they are not merged or ranked."}</p>
      <ul>{answer!.knowledge_sources!.map((k) => (
        <li key={k.label}>
          <strong>{k.label} {k.title}</strong>{k.position ? ` · ${k.position}` : ""}
          {" "}<span className={k.authority_class === "secondary_source" || k.authority_class === "primary_source" ? "status-pill status-implemented" : "status-pill status-not-verified"}>{AUTHORITY_LABEL[k.authority_class]?.[rtl ? "ar" : "en"]}</span>
          <p style={{ whiteSpace: "pre-line" }}>{k.text}</p>
          <small>{k.source_title}{k.author ? ` · ${k.author}` : ""}{k.edition ? ` · ${k.edition}` : ""} · {k.locator} · {k.license} · <code>{k.record.dataset}/{k.record.id}</code>{k.url ? <> · <a href={k.url} rel="noopener noreferrer nofollow">{rtl ? "المصدر" : "source"}</a></> : null}</small>
          <p className="tool-note">{k.verification_state}</p>
          {k.uncertainty.length > 0 && <p role="note" className="tool-note">{k.uncertainty.join("; ")}</p>}
        </li>))}
      </ul>
    </section>
  );

  return <main className="assistant-shell" dir={rtl ? "rtl" : "ltr"}>
    <header><h1>{copy.title}</h1><p>{copy.intro}</p></header>
    <form onSubmit={submit} aria-busy={busy}>
      <label htmlFor="assistant-question" className="sr-only">{copy.placeholder}</label>
      <textarea id="assistant-question" value={question} onChange={(e) => setQuestion(e.target.value)} placeholder={copy.placeholder} required maxLength={4000} />
      <label className="check"><input type="checkbox" checked={synthesis} onChange={(e) => setSynthesis(e.target.checked)} /> {copy.synthLabel}</label>
      <button disabled={busy || !question.trim()}>{busy ? "…" : copy.submit}</button>
    </form>
    <section aria-live="polite" aria-atomic="false">
      {answer?.status === "assembled" && <>
        {answer.confidence && <p className="tool-note">{copy.confidence}: {answer.confidence.level} ({answer.confidence.score})</p>}
        {section("primary_source", copy.primary, "primary")}
        {section("scholarly_explanation", copy.scholarly, "scholarly")}
        {section("secondary_source", copy.secondary, "secondary")}
        {answer.scholarly_views?.map((v) => <p key={v.reference} role="note" className="tool-note">{copy.views} {v.reference}: {v.views.map((x) => x.attribution).join(" · ")}. {v.note}</p>)}
        {answer.ai_synthesis && answer.ai_synthesis.status !== "not_requested" && (
          <section className="answer-section ai" aria-label={copy.ai}>
            <h3>{copy.ai}</h3>
            {answer.ai_synthesis.status === "validated" && <><p>{answer.ai_synthesis.text}</p><small>{copy.aiNotice}</small></>}
            {answer.ai_synthesis.status === "unavailable" && <p>{copy.aiUnavailable}</p>}
            {answer.ai_synthesis.status === "rejected" && <p>{copy.aiRejected}</p>}
          </section>
        )}
        <p className="assistant-boundary">{copy.boundary}</p>
      </>}
      {answer && knowledge}
      {answer?.status === "insufficient" && <p role="status"><strong>{INSUFFICIENT[rtl ? "ar" : "en"]}</strong> {AUTHORITY_LABEL.unavailable[rtl ? "ar" : "en"]}. {rtl ? "جرّب صياغة أخرى أو موضوعاً أعم." : "Try rephrasing, or a broader topic."}</p>}
    </section>
  </main>;
}
