"use client";
import { useCallback, useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import { COVERAGE_LABEL, DOMAIN_STATUS_LABEL, READINESS_LABEL } from "@/lib/copy";
import { ReviewQueues } from "@/components/review-queues";

type Dataset = { id: string; name: string; type: string; source: { name: string; url: string | null; version: string | null }; license: { name: string; status: string }; provenance: string;
  validation_status: string; publication_status: string; enabled: boolean; readiness: string; remaining_action: string | null; record_count: number; can_publish: boolean; cannot_publish_because: string[];
  rights_confirmation: Record<string, string> | null; importer: string | null; importer_version: string | null; checksum_sha256: string | null };
type Queue = { items: { id: string; name: string; type: string; city: string | null; country: string | null; source: string; license: string; provenance: string; status: string; duplicate_of: string | null }[] };
type Reports = { items: { id: string; listing_id: string; reason: string; details: string | null; created_at: string }[] };
type Runs = { runs: { id: string; created_at: string; classification: string; status: string; insufficiency_reason: string | null; claims: { type: string; status: string; text: string; rejection_reason: string | null; citations: { label: string }[] }[] }[] };
type Audit = { events: { id: string; action: string; target_type: string | null; metadata: Record<string, unknown>; at: string }[] };
type Preview = { rows: number; valid: number; would_create: number; would_update?: number; would_update_or_unchanged?: number; unchanged?: number; failed: number; failures: { index: number; id: string | null; errors: string[] }[] };
type History = { dataset: Dataset; imports: { id: string; adapter_id: string | null; source_version: string | null; source_checksum: string | null; at: string; status: string; created: number; updated: number; unchanged: number; failed: number; failures: { index: number; errors: string[] }[]; file_sha256: string }[]; events: { action: string; at: string; metadata: Record<string, unknown> }[] };
type Gate = { passed: boolean; evidence: string };
type DomainRow = { domain: string; label: string; status: string; declared_status: string; coverage: string; scope: string; source: string | null; source_url: string | null; source_version: string | null; licence: string | null;
  licence_evidence: string | null; provenance_confidence: string; data_quality_confidence: string; import_availability: string; last_successful_retrieval: string | null; records: { total: number; published: number; hidden: number };
  validation_status: string; publication_status: string; blockers: string[]; notes: string; verified_by: string; gates: Record<string, Gate>; registry_out_of_date: boolean;
  why_not_ready: { kind: string; text?: string; gate?: string; evidence?: string }[] };
type Readiness = { as_of: string; summary: Record<string, number>; domains: DomainRow[] };
type Importer = { id: string; dataset: string; title: string; licence: string; params: Record<string, string>; dataset_publication: string; license_status: string; probe: { all_reachable: boolean; urls: Record<string, string> } | null;
  last_run: { id: string; status: string; created: number; updated: number; unchanged: number; failed: number; source_version: string | null; source_checksum: string | null; source_retrieved_at: string | null; at: string } | null };
type RunResult = { adapter: string; source_version: string; source_checksum: string; skipped: Record<string, number>; preview: Preview; applied: boolean; status?: string; created?: number; updated?: number; failed?: number };
type Conflicts = { dataset: string; kind: string; totals: Record<string, number>; items: Record<string, Record<string, unknown>[]>; note: string };
type Tab = "readiness" | "datasets" | "importers" | "review" | "directory" | "reports" | "answers" | "audit";

export function AdminDataPanel({ locale }: { locale: "en" | "ar" }) {
  const ar = locale === "ar";
  const [tab, setTab] = useState<Tab>("readiness");
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [importers, setImporters] = useState<Importer[]>([]);
  const [runResult, setRunResult] = useState<RunResult | null>(null);
  const [conflicts, setConflicts] = useState<Conflicts | null>(null);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [queue, setQueue] = useState<Queue["items"]>([]);
  const [reports, setReports] = useState<Reports["items"]>([]);
  const [runs, setRuns] = useState<Runs["runs"]>([]);
  const [audit, setAudit] = useState<Audit["events"]>([]);
  const [msg, setMsg] = useState("");
  const [forbidden, setForbidden] = useState(false);
  const [staged, setStaged] = useState<{ dataset: Dataset; records: unknown[]; listings: boolean; preview: Preview } | null>(null);
  const [history, setHistory] = useState<History | null>(null);

  const load = useCallback(async () => {
    try {
      if (tab === "readiness") setReadiness(await apiFetch<Readiness>("/admin/datasets/readiness"));
      if (tab === "importers") setImporters((await apiFetch<{ importers: Importer[] }>("/admin/datasets/importers/list")).importers);
      if (tab === "datasets") setDatasets((await apiFetch<{ datasets: Dataset[] }>("/admin/datasets")).datasets);
      if (tab === "directory") setQueue((await apiFetch<Queue>("/directory/admin/queue?status=pending")).items);
      if (tab === "reports") setReports((await apiFetch<Reports>("/directory/admin/reports")).items);
      if (tab === "answers") setRuns((await apiFetch<Runs>("/assistant/admin/runs?limit=30")).runs);
      if (tab === "audit") setAudit((await apiFetch<Audit>("/admin/datasets/audit/events?limit=100")).events);
    } catch (e) { if (e instanceof ApiError && (e.status === 403 || e.status === 401)) setForbidden(true); else setMsg(e instanceof ApiError ? e.message : "Error"); }
  }, [tab]);
  useEffect(() => { void load(); }, [load]);

  async function act(path: string, body?: unknown) {
    setMsg("");
    try { await apiFetch(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }); setMsg(ar ? "تم." : "Done."); await load(); }
    catch (e) { setMsg(e instanceof ApiError ? `${e.message}${Array.isArray(e.details.reasons) ? " " + (e.details.reasons as string[]).join("; ") : ""}` : "Error"); }
  }
  async function datasetAction(d: Dataset, action: string) {
    const body: Record<string, string> = { action };
    if (action === "mark_verified") { const note = window.prompt(ar ? "ماذا راجعت؟ (10 أحرف على الأقل)" : "What did you check? (at least 10 characters)"); if (!note) return; body.note = note; }
    if (action === "publish" && !d.can_publish) {
      const by = window.prompt(ar ? "اسمك (تأكيد الحقوق)" : "Your name (rights confirmation)"); if (!by) return;
      const basis = window.prompt(ar ? "أساس الإذن (رخصة، إذن كتابي…)" : "Basis for permission (licence, written permission…)"); if (!basis) return;
      body.confirmed_by = by; body.confirmed_on = new Date().toISOString().slice(0, 10); body.basis = basis;
    }
    await act(`/admin/datasets/${d.id}/action`, body);
  }
  /** Step 1: read the file and ask the server to validate it. Nothing is written until the administrator confirms. */
  async function upload(d: Dataset, file: File, listings: boolean) {
    setMsg(""); setStaged(null);
    try {
      const parsed = JSON.parse(await file.text());
      const records = Array.isArray(parsed) ? parsed : parsed.records ?? parsed.listings;
      if (!Array.isArray(records)) throw new Error("not a list");
      const preview = await apiFetch<Preview>(`/admin/datasets/${d.id}/${listings ? "preview-listings" : "preview"}`, { method: "POST", body: JSON.stringify({ records }) });
      setStaged({ dataset: d, records, listings, preview });
    } catch (e) { setMsg(e instanceof ApiError ? e.message : ar ? "ملف غير صالح" : "Invalid file"); }
  }
  /** Step 2: import. The server refuses the whole file if any row is invalid (all-or-nothing). */
  async function confirmImport() {
    if (!staged) return;
    const { dataset, records, listings } = staged;
    try {
      const r = await apiFetch<{ status: string; created: number; updated: number; failed: number; failures: { index: number; errors: string[] }[] }>(`/admin/datasets/${dataset.id}/${listings ? "import-listings" : "import"}`, { method: "POST", body: JSON.stringify({ records }) });
      setMsg(r.status === "failed" ? (ar ? "رُفض الملف كله: لم يُكتب شيء." : "The whole file was rejected; nothing was written.") : `${ar ? "أُنشئ" : "Created"} ${r.created}, ${ar ? "حُدّث" : "updated"} ${r.updated}`);
      setStaged(null); await load();
    } catch (e) { setMsg(e instanceof ApiError ? e.message : "Error"); }
  }
  async function probe(id: string) {
    try {
      const r = await apiFetch<{ importers: Importer[] }>("/admin/datasets/importers/list?probe=true");
      setImporters(r.importers); setMsg(r.importers.find((i) => i.id === id)?.probe?.all_reachable ? (ar ? "المصدر متاح من هذا الخادم." : "The source is reachable from this server.") : (ar ? "المصدر غير متاح من هذا الخادم." : "The source is NOT reachable from this server."));
    } catch (e) { setMsg(e instanceof ApiError ? e.message : "Error"); }
  }
  async function runImporter(i: Importer, apply: boolean) {
    setMsg(""); setRunResult(null);
    const params: Record<string, string> = {};
    for (const key of Object.keys(i.params)) { const v = window.prompt(`${key}: ${i.params[key]}`); if (!v) return; params[key] = v; }
    try { setRunResult(await apiFetch<RunResult>(`/admin/datasets/importers/${i.id}/${apply ? "run" : "preview"}`, { method: "POST", body: JSON.stringify({ params }) })); if (apply) await load(); }
    catch (e) { setMsg(e instanceof ApiError ? e.message : "Error"); }
  }
  async function showConflicts(d: Dataset) {
    try { setConflicts(await apiFetch<Conflicts>(`/admin/datasets/${d.id}/conflicts?limit=25`)); } catch (e) { setMsg(e instanceof ApiError ? e.message : "Error"); }
  }
  async function showHistory(d: Dataset) {
    try { setHistory(await apiFetch<History>(`/admin/datasets/${d.id}/provenance`)); } catch (e) { setMsg(e instanceof ApiError ? e.message : "Error"); }
  }
  if (forbidden) return <main className="knowledge-page"><p role="alert">{ar ? "هذه الصفحة للمشرفين فقط." : "This page is for platform administrators."}</p></main>;
  const tabs: [Tab, string][] = [["readiness", ar ? "الجاهزية" : "Readiness"], ["importers", ar ? "المستوردات" : "Importers"], ["datasets", ar ? "مجموعات البيانات" : "Datasets"], ["review", ar ? "المراجعة البشرية" : "Human review"], ["directory", ar ? "مراجعة الدليل" : "Directory queue"], ["reports", ar ? "البلاغات" : "Reports"], ["answers", ar ? "إجابات الذكاء الاصطناعي" : "AI answers"], ["audit", ar ? "سجل التدقيق" : "Audit log"]];
  return (
    <main className="knowledge-page admin-panel" dir={ar ? "rtl" : "ltr"}>
      <h1>{ar ? "الثقة والبيانات" : "Data & trust"}</h1>
      <nav className="knowledge-types" role="tablist">{tabs.map(([id, label]) => <button key={id} role="tab" aria-selected={tab === id} className={tab === id ? "chip chip-active" : "chip"} onClick={() => setTab(id)}>{label}</button>)}</nav>
      {msg && <p role="status">{msg}</p>}
      {tab === "readiness" && (!readiness ? <p aria-busy="true">…</p> : (
        <>
          <p>{Object.entries(readiness.summary).map(([k, v]) => `${DOMAIN_STATUS_LABEL[k]?.[ar ? "ar" : "en"] ?? k}: ${v}`).join(" · ")}</p>
          <ul className="record-list">{readiness.domains.map((d) => (
            <li key={d.domain} className="record-card" data-testid={`readiness-${d.domain}`}>
              <h2>{d.label} <span className={`status-pill ${d.status === "READY" ? "status-implemented" : "status-not-verified"}`}>{DOMAIN_STATUS_LABEL[d.status]?.[ar ? "ar" : "en"] ?? d.status}</span> <small>{COVERAGE_LABEL[d.coverage]?.[ar ? "ar" : "en"]}</small></h2>
              <p>{d.scope}</p>
              <dl className="provenance">
                <div><dt>Source</dt><dd>{d.source ?? "none"}{d.source_version ? ` · ${d.source_version}` : ""}</dd></div>
                <div><dt>Licence</dt><dd>{d.licence ?? "none"}</dd></div>
                <div><dt>Records</dt><dd>{d.records.published} published · {d.records.hidden} hidden · {d.records.total} total{d.registry_out_of_date ? " (registry out of date)" : ""}</dd></div>
                <div><dt>Confidence</dt><dd>provenance {d.provenance_confidence} · quality {d.data_quality_confidence} · import {d.import_availability}</dd></div>
                <div><dt>Verified by</dt><dd>{d.verified_by}</dd></div>
              </dl>
              {d.status !== "READY" && (
                <details><summary>{ar ? "لماذا ليس جاهزاً" : "Why this is not READY"} ({d.why_not_ready.length})</summary>
                  <ul>{d.why_not_ready.map((w, i) => <li key={i}>{w.kind === "gate" ? <><strong>{w.gate}</strong>: {w.evidence}</> : w.text}</li>)}</ul></details>
              )}
            </li>))}
          </ul>
        </>
      ))}
      {tab === "review" && <ReviewQueues ar={ar} />}
      {tab === "importers" && (
        <>
          <p className="tool-note">{ar ? "المستوردات تعمل كلها أو لا شيء، ولا تنشر ولا توثّق. إعادة التشغيل آمنة." : "Importers are all-or-nothing, never publish and never verify. Re-running is safe: an unchanged source changes nothing."}</p>
          {runResult && (
            <section className="record-card" role="region" aria-label="Importer result" data-testid="importer-result">
              <h2>{runResult.adapter}: {runResult.applied ? (ar ? "طُبِّق" : "applied") : (runResult.status ?? (ar ? "معاينة" : "preview"))}</h2>
              <p>{runResult.source_version} · <code>{runResult.source_checksum.slice(0, 16)}…</code></p>
              <p>{runResult.preview.rows} {ar ? "صفوف" : "rows"} · {runResult.preview.valid} {ar ? "صالحة" : "valid"} · {runResult.preview.would_create} {ar ? "جديدة" : "new"} · {runResult.preview.failed} {ar ? "أخطاء" : "errors"} · {ar ? "متجاوَز" : "skipped"}: {JSON.stringify(runResult.skipped)}</p>
              {runResult.preview.failures.length > 0 && <ul>{runResult.preview.failures.slice(0, 10).map((f) => <li key={f.index}>#{f.index}: {f.errors.join("; ")}</li>)}</ul>}
            </section>
          )}
          <ul className="record-list">{importers.map((i) => (
            <li key={i.id} className="record-card">
              <h2>{i.title} <small>{i.id}</small></h2>
              <dl className="provenance">
                <div><dt>Dataset</dt><dd>{i.dataset} · {i.dataset_publication} · {i.license_status}</dd></div>
                <div><dt>Licence</dt><dd>{i.licence}</dd></div>
                <div><dt>Last run</dt><dd>{i.last_run ? `${i.last_run.at} · ${i.last_run.status} · +${i.last_run.created} ~${i.last_run.updated} =${i.last_run.unchanged} !${i.last_run.failed} · ${i.last_run.source_version ?? "no version"}` : "never"}</dd></div>
                {i.probe && <div><dt>Reachability</dt><dd>{Object.entries(i.probe.urls).map(([u, v]) => `${u}: ${v}`).join("; ")}</dd></div>}
              </dl>
              <div className="reader-actions">
                <button onClick={() => probe(i.id)}>{ar ? "فحص التوفر" : "Check reachability"}</button>
                <button onClick={() => runImporter(i, false)}>{ar ? "معاينة" : "Preview"}</button>
                <button onClick={() => runImporter(i, true)}>{ar ? "تشغيل" : "Run import"}</button>
              </div>
            </li>))}
          </ul>
        </>
      )}
      {tab === "datasets" && (
        <>
          <p><button onClick={() => act("/admin/datasets/manifest/sync")}>{ar ? "مزامنة البيان وتطبيق النشر" : "Sync manifest and apply publication"}</button></p>
          {staged && (
            <section className="record-card" role="region" aria-label={ar ? "معاينة الاستيراد" : "Import preview"}>
              <h2>{ar ? "معاينة" : "Preview"}: {staged.dataset.name}</h2>
              <p>{staged.preview.rows} {ar ? "صفوف" : "rows"} · {staged.preview.valid} {ar ? "صالحة" : "valid"} · {staged.preview.would_create} {ar ? "جديدة" : "new"} · {staged.preview.failed} {ar ? "أخطاء" : "errors"}</p>
              {staged.preview.failures.length > 0 && <ul>{staged.preview.failures.slice(0, 20).map((f) => <li key={f.index}>#{f.index}{f.id ? ` (${f.id})` : ""}: {f.errors.join("; ")}</li>)}</ul>}
              <p className="tool-note">{ar ? "الاستيراد كل شيء أو لا شيء، ولا ينشر أي بيانات: النشر خطوة منفصلة." : "Importing is all-or-nothing and never publishes: publishing is a separate step."}</p>
              <div className="reader-actions"><button disabled={staged.preview.failed > 0} onClick={confirmImport}>{ar ? "استيراد" : "Import"}</button><button onClick={() => setStaged(null)}>{ar ? "إلغاء" : "Cancel"}</button></div>
            </section>
          )}
          {conflicts && (
            <section className="record-card" role="region" aria-label={ar ? "التكرار والتعارض" : "Duplicates and conflicts"} data-testid="conflicts-panel">
              <h2>{conflicts.dataset}: {ar ? "التكرار والتعارض" : "duplicates and conflicts"}</h2>
              <p className="tool-note">{conflicts.note}</p>
              <p>{Object.entries(conflicts.totals).map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`).join(" · ")}</p>
              {Object.entries(conflicts.items).map(([k, list]) => list.length > 0 && <details key={k}><summary>{k.replace(/_/g, " ")} ({list.length} {ar ? "معروض" : "shown"})</summary><ul>{list.slice(0, 10).map((x, i) => <li key={i}><code>{JSON.stringify(x).slice(0, 220)}</code></li>)}</ul></details>)}
              <div className="reader-actions"><button onClick={() => setConflicts(null)}>{ar ? "إغلاق" : "Close"}</button></div>
            </section>
          )}
          {history && (
            <section className="record-card" role="region" aria-label={ar ? "سجل المجموعة" : "Dataset history"}>
              <h2>{history.dataset.name}: {ar ? "المنشأ والسجل" : "provenance and history"}</h2>
              <p>{history.dataset.provenance}</p>
              <h3>{ar ? "عمليات الاستيراد" : "Imports"}</h3>
              <ul>{history.imports.map((i) => <li key={i.id}>{i.at} · {i.adapter_id ?? "manual upload"} · {i.source_version ?? ""} · {i.status} · +{i.created} / ~{i.updated} / ={i.unchanged} / !{i.failed} · <code>{i.file_sha256.slice(0, 12)}…</code>{i.status === "applied" && <> <button onClick={() => act(`/admin/datasets/imports/${i.id}/rollback`)}>{ar ? "تراجع" : "Roll back"}</button></>}{i.failures.length > 0 && <small> — {i.failures[0].errors[0]}</small>}</li>)}</ul>
              <h3>{ar ? "الأحداث" : "Events"}</h3>
              <ul>{history.events.slice(0, 15).map((e, n) => <li key={n}>{e.at} · {e.action}</li>)}</ul>
              <div className="reader-actions"><button onClick={() => setHistory(null)}>{ar ? "إغلاق" : "Close"}</button></div>
            </section>
          )}
          <ul className="record-list">
            {datasets.map((d) => (
              <li key={d.id} className="record-card">
                <h2>{d.name} <small>{d.id}</small></h2>
                <p><span className={d.publication_status === "published" && d.enabled ? "status-pill status-implemented" : "status-pill status-architecture-ready"}>{d.publication_status}{d.enabled ? "" : " · disabled"}</span> <span className="status-pill status-not-verified">{READINESS_LABEL[d.readiness]?.en ?? d.readiness}</span> <small>{d.record_count} {ar ? "سجل" : "records"}</small></p>
                <dl className="provenance">
                  <div><dt>Source</dt><dd>{d.source.name}{d.source.version ? ` ${d.source.version}` : ""}{d.source.url ? <> · <a href={d.source.url} rel="noopener noreferrer nofollow">link</a></> : ""}</dd></div>
                  <div><dt>Licence</dt><dd>{d.license.name} <strong>({d.license.status})</strong></dd></div>
                  <div><dt>Validation</dt><dd>{d.validation_status}</dd></div>
                  <div><dt>Provenance</dt><dd>{d.provenance}</dd></div>
                  {d.checksum_sha256 && <div><dt>sha256</dt><dd><code>{d.checksum_sha256.slice(0, 16)}…</code></dd></div>}
                  {d.rights_confirmation && <div><dt>Rights confirmed</dt><dd>{JSON.stringify(d.rights_confirmation)}</dd></div>}
                  {d.remaining_action && <div><dt>Remaining</dt><dd>{d.remaining_action}</dd></div>}
                  {!d.can_publish && <div><dt>Cannot publish because</dt><dd>{d.cannot_publish_because.join("; ")}</dd></div>}
                </dl>
                <div className="reader-actions">
                  <button onClick={() => datasetAction(d, "mark_verified")}>{ar ? "اعتماد التحقق" : "Mark verified"}</button>
                  <button onClick={() => datasetAction(d, "publish")}>{ar ? "نشر" : "Publish"}</button>
                  <button onClick={() => datasetAction(d, "unpublish")}>{ar ? "إلغاء النشر" : "Unpublish"}</button>
                  <button onClick={() => showConflicts(d)}>{ar ? "التكرار والتعارض" : "Duplicates & conflicts"}</button>
                  <button onClick={() => showHistory(d)}>{ar ? "المنشأ والسجل" : "Provenance & history"}</button>
                  <button onClick={() => datasetAction(d, d.enabled ? "disable" : "enable")}>{d.enabled ? (ar ? "تعطيل" : "Disable") : (ar ? "تفعيل" : "Enable")}</button>
                  <button onClick={() => datasetAction(d, "reject")}>{ar ? "رفض" : "Reject"}</button>
                  <label className="upload">{ar ? "معاينة ملف (JSON)" : "Preview a JSON file"}<input type="file" accept=".json,application/json" onChange={(e) => { const f = e.target.files?.[0]; if (f) void upload(d, f, d.id.startsWith("directory-")); e.target.value = ""; }} /></label>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
      {tab === "directory" && (queue.length === 0 ? <p role="status">{ar ? "لا قوائم بانتظار المراجعة." : "Nothing is waiting for review."}</p> : (
        <ul className="record-list">{queue.map((l) => (
          <li key={l.id} className="record-card"><h2>{l.name}</h2><p className="tool-note">{l.type} · {[l.city, l.country].filter(Boolean).join(", ")} · {l.source} · {l.license}</p><p>{l.provenance}</p>{l.duplicate_of && <p role="note">{ar ? "مكرر محتمل لـ" : "Possible duplicate of"} {l.duplicate_of}</p>}
            <div className="reader-actions">{["approve", "reject", "hide"].map((a) => <button key={a} onClick={() => act(`/directory/admin/listings/${l.id}/moderate`, { action: a })}>{a}</button>)}</div></li>))}
        </ul>))}
      {tab === "reports" && (reports.length === 0 ? <p role="status">{ar ? "لا بلاغات مفتوحة." : "No open reports."}</p> : (
        <ul className="record-list">{reports.map((r) => (
          <li key={r.id} className="record-card"><h2>{r.reason}</h2><p>{r.details}</p><small>listing {r.listing_id} · {r.created_at}</small>
            <div className="reader-actions"><button onClick={() => act(`/directory/admin/reports/${r.id}/resolve`, { outcome: "actioned", hide_listing: true })}>{ar ? "إخفاء القائمة" : "Hide listing"}</button><button onClick={() => act(`/directory/admin/reports/${r.id}/resolve`, { outcome: "dismissed" })}>{ar ? "تجاهل" : "Dismiss"}</button></div></li>))}
        </ul>))}
      {tab === "answers" && (runs.length === 0 ? <p role="status">{ar ? "لا إجابات مسجلة." : "No answers recorded yet."}</p> : (
        <ul className="record-list">{runs.map((r) => (
          <li key={r.id} className="record-card"><h2>{r.status} · {r.classification}</h2><small>{r.created_at}{r.insufficiency_reason ? ` · ${r.insufficiency_reason}` : ""}</small>
            <ul>{r.claims.map((c, i) => <li key={i}><strong>{c.type}/{c.status}</strong> {c.citations.map((x) => x.label).join("")} — {c.text.slice(0, 160)}{c.rejection_reason ? ` (${c.rejection_reason})` : ""}</li>)}</ul></li>))}
        </ul>))}
      {tab === "audit" && (
        <table className="audit-table"><thead><tr><th>{ar ? "الوقت" : "When"}</th><th>{ar ? "الإجراء" : "Action"}</th><th>{ar ? "التفاصيل" : "Details"}</th></tr></thead>
          <tbody>{audit.map((e) => <tr key={e.id}><td>{e.at}</td><td>{e.action}</td><td><code>{JSON.stringify(e.metadata)}</code></td></tr>)}</tbody></table>
      )}
    </main>
  );
}
