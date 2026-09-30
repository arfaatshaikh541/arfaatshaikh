"use client";
import { FormEvent, useState } from "react";
import { apiFetch } from "@/lib/api";

type Result = { status: "found" | "not_found" | "too_short"; query_words: number; matches: { corpus: string; reference: string }[]; note?: string };

export function TextVerifier({ locale }: { locale: "en" | "ar" }) {
  const ar = locale === "ar";
  const [text, setText] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError(false); setResult(null);
    try { setResult(await apiFetch<Result>("/verification/text", { method: "POST", body: JSON.stringify({ text }) })); }
    catch { setError(true); } finally { setBusy(false); }
  }
  return (
    <div className="governance-checker">
      <form onSubmit={submit} className="governance-form" aria-busy={busy}>
        <label htmlFor="verify-text">{ar ? "الصق نصاً عربياً (ثلاث كلمات فأكثر)" : "Paste Arabic text (three words or more)"}</label>
        <textarea id="verify-text" dir="rtl" lang="ar" rows={5} maxLength={4000} value={text} onChange={(e) => setText(e.target.value)} required />
        <button disabled={busy || !text.trim()}>{busy ? "…" : ar ? "تحقق" : "Check"}</button>
      </form>
      {error && <p role="alert">{ar ? "تعذّر إجراء التحقق." : "The check could not be completed."}</p>}
      {result && (
        <section role="status" aria-live="polite">
          {result.status === "too_short" && <p>{ar ? "النص قصير جداً. أدخل ثلاث كلمات على الأقل." : "That text is too short. Enter at least three words."}</p>}
          {result.status === "not_found" && <p className="tool-value">{ar ? "لم يُعثر على هذا النص في القرآن أو كتب الحديث المنشورة." : "This text was not found in the published Qur’an or Hadith text."}</p>}
          {result.status === "found" && <>
            <p className="tool-value">{ar ? "وُجد النص في:" : "Found in:"}</p>
            <ul className="plain-list">{result.matches.map((m) => <li key={m.reference}>{m.reference}</li>)}</ul>
          </>}
          {result.note && <p className="tool-note">{result.note}</p>}
        </section>
      )}
    </div>
  );
}
