"use client";

import { FormEvent, useState } from "react";
import { apiFetch } from "@/lib/api";

type Evidence = { label: string; canonical_reference: string; attribution: string; exact_text: string };
type Answer = { status: string; response_text?: string | null; insufficiency_reason?: string | null; evidence?: Evidence[] };

export function IslamicAssistant({ locale }: { locale: "en" | "ar" }) {
  const rtl = locale === "ar";
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [busy, setBusy] = useState(false);
  const copy = rtl ? {
    title: "المساعد الإسلامي الموثّق", intro: "إجابات مبنية على مصادر منشورة ومعتمدة، مع إظهار الأدلة بوضوح.",
    placeholder: "اكتب سؤالك…", submit: "بحث وإجابة", sources: "المصادر", insufficient: "لا توجد أدلة معتمدة كافية للإجابة بثقة.", boundary: "لا تُعد الإجابة فتوى شخصية."
  } : {
    title: "Evidence-grounded Islamic assistant", intro: "Answers are assembled from approved, published sources with inspectable evidence.",
    placeholder: "Ask an Islamic question…", submit: "Find grounded answer", sources: "Sources", insufficient: "There is not enough approved evidence to answer confidently.", boundary: "This is not a personal fatwa."
  };

  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setAnswer(null);
    try {
      setAnswer(await apiFetch<Answer>("/assistant/query", { method: "POST", body: JSON.stringify({ question, locale }) }));
    } catch { setAnswer({ status: "insufficient", insufficiency_reason: "request_failed" }); }
    finally { setBusy(false); }
  }

  return <main className="assistant-shell" dir={rtl ? "rtl" : "ltr"}>
    <header><h1>{copy.title}</h1><p>{copy.intro}</p></header>
    <form onSubmit={submit} aria-busy={busy}>
      <label htmlFor="assistant-question" className="sr-only">{copy.placeholder}</label>
      <textarea id="assistant-question" value={question} onChange={(e) => setQuestion(e.target.value)} placeholder={copy.placeholder} required maxLength={4000} />
      <button disabled={busy || !question.trim()}>{busy ? "…" : copy.submit}</button>
    </form>
    <section aria-live="polite" aria-atomic="false">
      {answer?.status === "assembled" && <article><p className="assistant-answer">{answer.response_text}</p><p className="assistant-boundary">{copy.boundary}</p></article>}
      {answer?.status === "insufficient" && <p role="status">{copy.insufficient}</p>}
    </section>
    {!!answer?.evidence?.length && <aside aria-labelledby="assistant-sources"><h2 id="assistant-sources">{copy.sources}</h2>{answer.evidence.map((item) => <details key={item.label}><summary>{item.label} {item.canonical_reference} · {item.attribution}</summary><blockquote lang={rtl ? "ar" : undefined}>{item.exact_text}</blockquote></details>)}</aside>}
  </main>;
}
