"use client";
import { useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";

type ZakatFundResult = { allowed: boolean; reason_codes: string[]; policy_version: string; status: string };

async function sha256Hex(input: string): Promise<string> {
  const bytes = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

const REASON_LABEL: Record<string, { en: string; ar: string }> = {
  scholarly_policy_approval_required: { en: "A scholarly-approved distribution policy is required.", ar: "يلزم وجود سياسة توزيع معتمدة شرعياً." },
  independent_trustee_threshold_not_met: { en: "At least two independent trustees are required.", ar: "يلزم وجود أمينين مستقلين على الأقل." },
  segregated_accounts_required: { en: "Zakat funds must be held in segregated accounts.", ar: "يجب حفظ أموال الزكاة في حسابات مستقلة." },
  audit_frequency_out_of_bounds: { en: "Audit frequency must be between 1 and 365 days.", ar: "يجب أن تكون دورية التدقيق بين يوم و365 يومًا." },
  eligible_beneficiary_categories_required: { en: "Eligible beneficiary categories (asnaf) must be configured.", ar: "يجب تحديد فئات المستحقين (الأصناف)." },
  administrative_cost_above_policy_limit: { en: "Administrative cost exceeds the 12% policy limit.", ar: "التكلفة الإدارية تتجاوز الحد المسموح 12%." },
  valid_evidence_fingerprint_required: { en: "A valid evidence fingerprint is required.", ar: "يلزم بصمة أدلة صالحة." },
  zakat_fund_allowed: { en: "This fund configuration passes governance acceptance.", ar: "يجتاز إعداد هذا الصندوق معايير الحوكمة." },
};

export function ZakatFundChecker({ locale }: { locale: "en" | "ar" }) {
  const ar = locale === "ar";
  const [form, setForm] = useState({
    scholarly_policy_approved: false,
    independent_trustees: 2,
    segregated_accounts: false,
    audit_frequency_days: 90,
    beneficiary_categories_configured: false,
    administrative_cost_percent: 10,
  });
  const [result, setResult] = useState<ZakatFundResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const evidence_sha256 = await sha256Hex(JSON.stringify(form) + Date.now());
      const response = await apiFetch<ZakatFundResult>("/ummah-services/zakat/funds/evaluate", {
        method: "POST",
        body: JSON.stringify({ ...form, evidence_sha256 }),
      });
      setResult(response);
    } catch (err) {
      setError(err instanceof ApiError && err.status === 401
        ? ar ? "سجّل الدخول لاستخدام أداة التحقق." : "Sign in to use the checker."
        : ar ? "تعذّر إجراء التحقق." : "The check could not be completed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="governance-checker">
      <p className="tool-note">
        {ar
          ? "تحقق من سياسة توزيع صندوق الزكاة مقابل قواعد القبول. هذه أداة تحقق، وليست نظام إدارة أموال زكاة."
          : "Checks a zakat fund's distribution policy against acceptance rules. This is a compliance check, not a fund management system."}
      </p>
      <form onSubmit={submit} className="governance-form">
        <label className="governance-check">
          <input type="checkbox" checked={form.scholarly_policy_approved} onChange={(e) => setForm((f) => ({ ...f, scholarly_policy_approved: e.target.checked }))} />
          {ar ? "سياسة توزيع معتمدة شرعياً" : "Scholarly-approved distribution policy"}
        </label>
        <label>
          {ar ? "عدد الأمناء المستقلين" : "Independent trustees"}
          <input type="number" min={0} value={form.independent_trustees} onChange={(e) => setForm((f) => ({ ...f, independent_trustees: Number(e.target.value) }))} />
        </label>
        <label className="governance-check">
          <input type="checkbox" checked={form.segregated_accounts} onChange={(e) => setForm((f) => ({ ...f, segregated_accounts: e.target.checked }))} />
          {ar ? "حسابات مستقلة لأموال الزكاة" : "Segregated zakat accounts"}
        </label>
        <label>
          {ar ? "دورية التدقيق (أيام)" : "Audit frequency (days)"}
          <input type="number" min={0} value={form.audit_frequency_days} onChange={(e) => setForm((f) => ({ ...f, audit_frequency_days: Number(e.target.value) }))} />
        </label>
        <label className="governance-check">
          <input type="checkbox" checked={form.beneficiary_categories_configured} onChange={(e) => setForm((f) => ({ ...f, beneficiary_categories_configured: e.target.checked }))} />
          {ar ? "فئات المستحقين (الأصناف الثمانية) محددة" : "Eligible beneficiary categories (asnaf) configured"}
        </label>
        <label>
          {ar ? "نسبة التكلفة الإدارية (%)" : "Administrative cost (%)"}
          <input type="number" min={0} max={100} value={form.administrative_cost_percent} onChange={(e) => setForm((f) => ({ ...f, administrative_cost_percent: Number(e.target.value) }))} />
        </label>
        <button type="submit" disabled={busy}>{busy ? (ar ? "جارٍ التحقق…" : "Checking…") : ar ? "تحقق من القبول" : "Check acceptance"}</button>
      </form>
      {error && <p role="alert" className="global-search-error">{error}</p>}
      {result && (
        <div className={`governance-result governance-result-${result.allowed ? "pass" : "fail"}`} role="status">
          <p className="governance-result-headline">
            {result.allowed
              ? (ar ? "✓ يجتاز معايير القبول" : "✓ Passes acceptance criteria")
              : (ar ? "✗ لا يجتاز معايير القبول" : "✗ Does not pass acceptance criteria")}
          </p>
          <ul>
            {result.reason_codes.map((code) => (
              <li key={code}>{REASON_LABEL[code]?.[ar ? "ar" : "en"] ?? code}</li>
            ))}
          </ul>
          <p className="tool-note">{ar ? `إصدار السياسة: ${result.policy_version} · الحالة: ${result.status}` : `Policy version: ${result.policy_version} · Status: ${result.status}`}</p>
        </div>
      )}
    </div>
  );
}
