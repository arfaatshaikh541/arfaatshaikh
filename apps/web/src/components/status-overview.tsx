"use client";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { COVERAGE_LABEL, DOMAIN_STATUS_LABEL, READINESS_LABEL } from "@/lib/copy";
import { allFeatures, featureCounts, STATUS_ORDER, type FeatureStatus } from "@/lib/worlds";

type Manifest = { as_of: string; datasets: { id: string; name: string; license: { name: string; status: string }; provenance: string; validation_status: string; readiness: string; public: boolean; remaining_action: string | null; source: { name: string; version: string | null } }[] };

const STATUS_TEXT: Record<FeatureStatus, { en: string; ar: string }> = {
  IMPLEMENTED: { en: "Implemented", ar: "مُنجز" }, PARTIALLY_IMPLEMENTED: { en: "Partly implemented", ar: "منجز جزئياً" }, NOT_VERIFIED: { en: "Not yet verified", ar: "لم يُتحقق منه" },
  DATA_SOURCE_REQUIRED: { en: "Data source required", ar: "يتطلب مصدر بيانات" }, ARCHITECTURE_READY: { en: "Ready for data", ar: "جاهز للبيانات" }, NOT_IMPLEMENTED: { en: "Not built", ar: "غير مبني" },
};

type DomainRow = { domain: string; label: string; tier: number; status: string; coverage: string; scope: string; coverage_note: string | null; source: string | null; licence: string | null;
  records: { total: number; published: number; hidden: number }; validation_status: string; blockers: string[]; verified_by: string; last_verified: string;
  why_not_ready: { kind: string; text?: string; gate?: string; evidence?: string }[] };
type Domains = { as_of: string; summary: Record<string, number>; domains: DomainRow[] };
type CoverageRow = { domain: string; coverage_status: string; geographic: boolean; countries?: { code: string; name: string; published: number }[]; statement: string };
type Coverage = { domains: CoverageRow[]; statement: string };

function coverageText(c: CoverageRow | undefined, ar: boolean): string {
  if (!c) return "";
  const names = (c.countries ?? []).map((x) => x.name).join(", ");
  if (c.coverage_status === "GLOBAL") return ar ? "منشور، غير مرتبط بمكان" : "Published; not tied to a place";
  if (c.coverage_status === "NO_VERIFIED_DATA") return ar ? "لا بيانات موثقة" : "No verified data";
  if (c.coverage_status === "HIDDEN_PENDING_RIGHTS") return ar ? "مستورد ومخفي حتى تثبت الحقوق" : "Imported, hidden until rights are established";
  if (c.coverage_status === "REGIONAL") return (ar ? "دول محددة فقط: " : "Only these countries: ") + names;
  return (ar ? "بلد واحد فقط: " : "One country only: ") + names;
}

export function StatusOverview({ locale }: { locale: "en" | "ar" }) {
  const ar = locale === "ar";
  const counts = featureCounts();
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [domains, setDomains] = useState<Domains | null>(null);
  const [coverage, setCoverage] = useState<Record<string, CoverageRow>>({});
  const [filter, setFilter] = useState<FeatureStatus | "ALL">("ALL");
  useEffect(() => { apiFetch<Domains>("/knowledge/domains").then(setDomains).catch(() => undefined); }, []);
  useEffect(() => { apiFetch<Coverage>("/knowledge/coverage").then((c) => setCoverage(Object.fromEntries(c.domains.map((d) => [d.domain, d])))).catch(() => undefined); }, []);
  useEffect(() => { apiFetch<Manifest>("/knowledge/manifest").then(setManifest).catch(() => undefined); }, []);
  const features = allFeatures().filter((f) => filter === "ALL" || f.status === filter);
  return (
    <main className="knowledge-page" dir={ar ? "rtl" : "ltr"}>
      <h1>{ar ? "الحالة الصادقة للمنصة" : "Honest platform status"}</h1>
      <p className="tool-note">{ar ? "ما هو منجز وما ينتظر بيانات أو ترخيصاً، دون ادعاء." : "What is built, and what is waiting for data or a licence, without overstating."}</p>
      <section aria-label={ar ? "جاهزية البيانات حسب المجال" : "Data readiness by domain"}>
        <h2>{ar ? "جاهزية البيانات حسب المجال" : "Data readiness by domain"}</h2>
        <p className="tool-note">{ar ? "لا يُعرض «جاهز» إلا إذا استوفى المجال كل شروط الجاهزية. وجود أداة استيراد أو بيانات لا يكفي." : "A domain shows Ready only when every readiness gate is met. An importer, or data being present, is not enough."}</p>
        {!domains && <p aria-busy="true">…</p>}
        {domains && (
          <>
            <p>{Object.entries(domains.summary).map(([k, v]) => `${DOMAIN_STATUS_LABEL[k]?.[ar ? "ar" : "en"] ?? k}: ${v}`).join(" · ")}</p>
            <div className="table-scroll" tabIndex={0} role="region" aria-label={ar ? "جدول جاهزية المجالات" : "Domain readiness table"}><table className="audit-table" data-testid="domain-dashboard">
              <thead><tr><th>{ar ? "المجال" : "Domain"}</th><th>{ar ? "الحالة" : "Status"}</th><th>{ar ? "السجلات" : "Records"}</th><th>{ar ? "المصدر والترخيص" : "Source and licence"}</th><th>{ar ? "لماذا ليس جاهزاً" : "Why not ready"}</th></tr></thead>
              <tbody>{domains.domains.map((d) => (
                <tr key={d.domain}>
                  <td><strong>{d.label}</strong><br /><small>{d.scope}</small></td>
                  <td><span className={`status-pill ${d.status === "READY" ? "status-implemented" : d.status === "PUBLISHED" ? "status-partially-implemented" : "status-not-verified"}`}>{DOMAIN_STATUS_LABEL[d.status]?.[ar ? "ar" : "en"] ?? d.status}</span><br /><small>{COVERAGE_LABEL[d.coverage]?.[ar ? "ar" : "en"]}</small><br /><small data-testid={`coverage-${d.domain}`}>{coverageText(coverage[d.domain], ar)}</small></td>
                  <td>{d.records.published} / {d.records.total}<br /><small>{ar ? "منشور / الكل" : "published / total"}</small></td>
                  <td>{d.source ?? "—"}<br /><small>{d.licence ?? ""}</small></td>
                  <td>{d.status === "READY" ? "—" : <ul>{d.blockers.slice(0, 3).map((b, i) => <li key={i}><small>{b}</small></li>)}{d.blockers.length === 0 && <li><small>{d.why_not_ready.find((w) => w.kind === "gate")?.evidence}</small></li>}</ul>}</td>
                </tr>))}</tbody>
            </table></div>
            <p className="tool-note">{ar ? "تحقّقٌ آلي فقط؛ لم تتم مراجعة بشرية علمية أو قانونية." : "Automated checks only; no human scholarly or legal review has taken place."} {domains.as_of}</p>
          </>
        )}
      </section>
      <section aria-label={ar ? "ملخص القدرات" : "Capability summary"}>
        <div className="knowledge-types">
          <button className={filter === "ALL" ? "chip chip-active" : "chip"} onClick={() => setFilter("ALL")}>{ar ? "الكل" : "All"} ({counts.total})</button>
          {STATUS_ORDER.map((s) => <button key={s} className={filter === s ? "chip chip-active" : "chip"} onClick={() => setFilter(s)}>{STATUS_TEXT[s][ar ? "ar" : "en"]} ({counts.byStatus[s]})</button>)}
        </div>
        <ul className="feature-list">{features.map((f, i) => <li key={`${f.id}-${i}`} className="feature-item"><div className="feature-list-head"><h2>{f.name}</h2><span className={`status-pill status-${f.status.toLowerCase().replaceAll("_", "-")}`}>{STATUS_TEXT[f.status][ar ? "ar" : "en"]}</span></div><p>{f.note}</p></li>)}</ul>
      </section>
      <section aria-label={ar ? "المصادر" : "Sources"}>
        <h2>{ar ? "المصادر والتراخيص" : "Sources and licences"}</h2>
        {!manifest && <p aria-busy="true">…</p>}
        {manifest && (
          <div className="table-scroll" tabIndex={0} role="region" aria-label={ar ? "جدول المصادر" : "Sources table"}><table className="audit-table"><thead><tr><th>{ar ? "المصدر" : "Source"}</th><th>{ar ? "الترخيص" : "Licence"}</th><th>{ar ? "الحالة" : "Status"}</th><th>{ar ? "عام" : "Public"}</th></tr></thead>
            <tbody>{manifest.datasets.map((d) => <tr key={d.id}><td><strong>{d.name}</strong><br /><small>{d.source.name}{d.source.version ? ` ${d.source.version}` : ""}</small></td><td>{d.license.name}<br /><small>{d.license.status}</small></td><td>{READINESS_LABEL[d.readiness]?.[ar ? "ar" : "en"] ?? d.readiness}{d.remaining_action ? <><br /><small>{d.remaining_action}</small></> : null}</td><td>{d.public ? (ar ? "نعم" : "Yes") : (ar ? "لا" : "No")}</td></tr>)}</tbody></table></div>
        )}
      </section>
    </main>
  );
}
