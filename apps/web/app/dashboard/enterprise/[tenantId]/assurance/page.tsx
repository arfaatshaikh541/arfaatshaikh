"use client";

import { use, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api, ApiError, type EnterpriseMembership } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

interface CorrelatedHealth {
  deployment_availability_percentage: number;
  deployment_sample_size: number;
  network_provisioning_percentage: number;
  network_sample_size: number;
  attestation_success_percentage: number;
  attestation_sample_size: number;
  policy_compliance_rate_percentage: number;
  policy_sample_size: number;
  open_incident_count: number;
  firing_alert_count: number;
}

interface SLODefinition {
  id: string;
  name: string;
  metric_source: string;
  target_percentage: number;
  window_days: number;
  status: string;
}

interface SLOEvaluation {
  id: string;
  evaluated_at: string;
  actual_percentage: number;
  error_budget_remaining_percentage: number;
  status: string;
  sample_size: number;
}

interface Incident {
  id: string;
  title: string;
  description: string;
  severity: string;
  status: string;
  opened_at: string;
}

interface IncidentEvent {
  id: string;
  event_type: string;
  detail: Record<string, unknown>;
  created_at: string;
}

interface CorrelatedAuditEvent {
  id: string;
  occurred_at: string;
  action: string;
}

interface AlertRule {
  id: string;
  name: string;
  metric_source: string;
  comparison: string;
  threshold: number;
  severity: string;
  status: string;
}

interface Alert {
  id: string;
  alert_rule_id: string;
  status: string;
  value_at_fire: number;
  fired_at: string;
  resolved_at?: string;
}

const METRIC_SOURCES = ["deployment_availability", "network_reservation_provisioning", "attestation_success_rate", "policy_compliance_rate"];

// Roles known (from docs/security/permission-matrix.md) to hold the
// server-side assurance.view / slos.manage / incidents.view /
// incidents.manage permissions -- a UX convenience only, re-checked
// independently by control-api on every request.
const CAN_VIEW = new Set(["enterprise_owner", "enterprise_admin", "ai_platform_engineer", "devops_engineer", "finops_manager", "read_only_auditor"]);
const CAN_MANAGE_SLOS = new Set(["enterprise_owner", "enterprise_admin", "ai_platform_engineer", "devops_engineer"]);
const CAN_VIEW_INCIDENTS = new Set(["enterprise_owner", "enterprise_admin", "devops_engineer", "compliance_manager", "security_administrator", "read_only_auditor"]);
const CAN_MANAGE_INCIDENTS = new Set(["enterprise_owner", "enterprise_admin", "security_administrator"]);

export default function EnterpriseAssurancePage({ params }: { params: Promise<{ tenantId: string }> }) {
  const { tenantId } = use(params);
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const members = useQuery({
    queryKey: ["tenant-members", tenantId],
    queryFn: () => api.get<EnterpriseMembership[]>(`/api/v1/enterprises/${tenantId}/members`),
  });
  const myRole = members.data?.find((m) => m.user_id === user?.user_id)?.role_key ?? "";
  const canView = CAN_VIEW.has(myRole);
  const canManageSLOs = CAN_MANAGE_SLOS.has(myRole);
  const canViewIncidents = CAN_VIEW_INCIDENTS.has(myRole);
  const canManageIncidents = CAN_MANAGE_INCIDENTS.has(myRole);

  const health = useQuery({
    queryKey: ["assurance-health", tenantId],
    queryFn: () => api.get<CorrelatedHealth>(`/api/v1/enterprises/${tenantId}/health`),
    enabled: canView,
  });
  const slos = useQuery({
    queryKey: ["slos", tenantId],
    queryFn: () => api.get<SLODefinition[]>(`/api/v1/enterprises/${tenantId}/slos`),
    enabled: canView,
  });
  const incidents = useQuery({
    queryKey: ["incidents", tenantId],
    queryFn: () => api.get<Incident[]>(`/api/v1/enterprises/${tenantId}/incidents`),
    enabled: canViewIncidents,
  });
  const alertRules = useQuery({
    queryKey: ["alert-rules", tenantId],
    queryFn: () => api.get<AlertRule[]>(`/api/v1/enterprises/${tenantId}/alert-rules`),
    enabled: canView,
  });
  const alerts = useQuery({
    queryKey: ["alerts", tenantId],
    queryFn: () => api.get<Alert[]>(`/api/v1/enterprises/${tenantId}/alerts`),
    enabled: canView,
  });

  const invalidate = (key: string) => queryClient.invalidateQueries({ queryKey: [key, tenantId] });

  if (members.isError && members.error instanceof ApiError && members.error.status === 403) {
    return (
      <main id="main-content" className="mx-auto w-full max-w-3xl flex-1 p-4 sm:p-8">
        <p>You do not have access to this tenant&apos;s service assurance data.</p>
        <Link href="/dashboard" className="underline">Back to dashboard</Link>
      </main>
    );
  }

  return (
    <main id="main-content" className="mx-auto w-full max-w-3xl flex-1 p-4 sm:p-8">
      <Link href={`/dashboard/enterprise/${tenantId}`} className="text-sm underline">&larr; Tenant overview</Link>
      <h1 className="mt-2 mb-1 text-2xl font-semibold">Service assurance</h1>
      <p className="mb-6 text-sm text-zinc-500">
        Every metric below is read directly from data GRIDKEEP already records for other reasons
        (deployment execution, network provisioning, attestation, sovereignty policy) -- nothing
        here is a separate, duplicated telemetry stream. SLO and alert evaluation run on demand;
        there is no live background scheduler in this environment.
      </p>

      {canView && health.data && (
        <section className="mb-8">
          <h2 className="mb-3 text-lg font-medium">Correlated health (last 24h)</h2>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <HealthTile label="Deployment availability" pct={health.data.deployment_availability_percentage} n={health.data.deployment_sample_size} />
            <HealthTile label="Network provisioning" pct={health.data.network_provisioning_percentage} n={health.data.network_sample_size} />
            <HealthTile label="Attestation success" pct={health.data.attestation_success_percentage} n={health.data.attestation_sample_size} />
            <HealthTile label="Policy compliance" pct={health.data.policy_compliance_rate_percentage} n={health.data.policy_sample_size} />
          </div>
          <p className="mt-2 text-xs text-zinc-500">
            {health.data.open_incident_count} open incident(s) &middot; {health.data.firing_alert_count} firing alert(s)
          </p>
        </section>
      )}

      {canView && (
        <section className="mb-8">
          <h2 className="mb-3 text-lg font-medium">SLOs</h2>
          <ul className="flex flex-col gap-2">
            {slos.data?.map((s) => (
              <SLORow key={s.id} tenantId={tenantId} slo={s} canManage={canManageSLOs} onChanged={() => invalidate("slos")} />
            ))}
            {slos.data?.length === 0 && <li className="text-sm text-zinc-500">No SLOs defined yet.</li>}
          </ul>
          {canManageSLOs && <CreateSLOForm tenantId={tenantId} onCreated={() => invalidate("slos")} />}
        </section>
      )}

      {canViewIncidents && (
        <section className="mb-8">
          <h2 className="mb-3 text-lg font-medium">Incidents</h2>
          <ul className="flex flex-col gap-2">
            {incidents.data?.map((i) => (
              <IncidentRow key={i.id} tenantId={tenantId} incident={i} canManage={canManageIncidents} onChanged={() => invalidate("incidents")} />
            ))}
            {incidents.data?.length === 0 && <li className="text-sm text-zinc-500">No incidents on record.</li>}
          </ul>
          {canManageIncidents && <CreateIncidentForm tenantId={tenantId} onCreated={() => invalidate("incidents")} />}
        </section>
      )}

      {canView && (
        <section className="mb-8">
          <h2 className="mb-3 text-lg font-medium">Alert rules</h2>
          <ul className="flex flex-col gap-2">
            {alertRules.data?.map((r) => (
              <AlertRuleRow key={r.id} tenantId={tenantId} rule={r} canManage={canManageSLOs}
                onChanged={() => { invalidate("alert-rules"); invalidate("alerts"); }} />
            ))}
            {alertRules.data?.length === 0 && <li className="text-sm text-zinc-500">No alert rules defined yet.</li>}
          </ul>
          {canManageSLOs && <CreateAlertRuleForm tenantId={tenantId} onCreated={() => invalidate("alert-rules")} />}
        </section>
      )}

      {canView && (
        <section>
          <h2 className="mb-3 text-lg font-medium">Alert history</h2>
          <ul className="flex flex-col gap-2 text-sm">
            {alerts.data?.map((a) => (
              <li key={a.id} className="rounded-lg border border-zinc-200 px-4 py-2 dark:border-zinc-800">
                <div className="flex items-center justify-between flex-wrap gap-1">
                  <span>value {a.value_at_fire}</span>
                  <span className={a.status === "firing" ? "text-red-600" : "text-zinc-500"}>{a.status}</span>
                </div>
                <p className="mt-1 text-xs text-zinc-500">Fired {new Date(a.fired_at).toLocaleString()}</p>
              </li>
            ))}
            {alerts.data?.length === 0 && <li className="text-zinc-500">No alerts have fired yet.</li>}
          </ul>
        </section>
      )}
    </main>
  );
}

function HealthTile({ label, pct, n }: { label: string; pct: number; n: number }) {
  return (
    <div className="rounded-lg border border-zinc-200 px-3 py-2 dark:border-zinc-800">
      <p className="text-xs text-zinc-500">{label}</p>
      <p className="text-lg font-medium">{pct.toFixed(1)}%</p>
      <p className="text-xs text-zinc-500">{n} sample(s)</p>
    </div>
  );
}

function SLORow({ tenantId, slo, canManage, onChanged }: { tenantId: string; slo: SLODefinition; canManage: boolean; onChanged: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const [lastEval, setLastEval] = useState<SLOEvaluation | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);

  const history = useQuery({
    queryKey: ["slo-evaluations", slo.id],
    queryFn: () => api.get<SLOEvaluation[]>(`/api/v1/enterprises/${tenantId}/slos/${slo.id}/evaluations`),
    enabled: historyOpen,
  });

  const evaluate = async () => {
    setError(null);
    try {
      const res = await api.post<SLOEvaluation>(`/api/v1/enterprises/${tenantId}/slos/${slo.id}/evaluate`, {});
      setLastEval(res);
      if (historyOpen) history.refetch();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to evaluate SLO.");
    }
  };

  const archive = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/slos/${slo.id}/archive`, {});
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to archive SLO.");
    }
  };

  return (
    <li className="rounded-lg border border-zinc-200 px-4 py-2 text-sm dark:border-zinc-800">
      <div className="flex items-center justify-between flex-wrap gap-1">
        <span className="font-medium">{slo.name}</span>
        <span className="text-zinc-500">{slo.status}</span>
      </div>
      <p className="mt-1 text-xs text-zinc-500">
        {slo.metric_source} &middot; target {slo.target_percentage}% over {slo.window_days}d
      </p>
      {lastEval && (
        <p className="mt-1 text-xs">
          Latest: {lastEval.actual_percentage.toFixed(1)}% ({lastEval.sample_size} samples) &middot;{" "}
          <span className={lastEval.status === "breached" ? "text-red-600" : lastEval.status === "at_risk" ? "text-amber-600" : "text-emerald-600"}>
            {lastEval.status}
          </span>
        </p>
      )}
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="mt-2 flex gap-3 flex-wrap">
        <button onClick={evaluate} className="text-xs underline">Evaluate now</button>
        <button onClick={() => setHistoryOpen(!historyOpen)} className="text-xs underline">
          {historyOpen ? "Hide history" : "Evaluation history"}
        </button>
        {canManage && slo.status === "active" && (
          <button onClick={archive} className="text-xs text-red-600 underline">Archive</button>
        )}
      </div>
      {historyOpen && (
        <ul className="mt-2 flex flex-col gap-1 rounded border border-zinc-100 p-2 text-xs dark:border-zinc-900">
          {history.data?.map((e) => (
            <li key={e.id} className="flex items-center justify-between flex-wrap gap-1">
              <span>{new Date(e.evaluated_at).toLocaleString()}</span>
              <span>{e.actual_percentage.toFixed(1)}% ({e.sample_size} samples) &middot; {e.status}</span>
            </li>
          ))}
          {history.data?.length === 0 && <li className="text-zinc-500">No evaluations recorded yet.</li>}
        </ul>
      )}
    </li>
  );
}

function CreateSLOForm({ tenantId, onCreated }: { tenantId: string; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [metricSource, setMetricSource] = useState(METRIC_SOURCES[0]);
  const [targetPercentage, setTargetPercentage] = useState("99");
  const [windowDays, setWindowDays] = useState("7");
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/slos`, {
        name, metric_source: metricSource, target_percentage: Number(targetPercentage), window_days: Number(windowDays),
      });
      setName("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create SLO.");
    }
  };

  return (
    <div className="mt-3 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h3 className="mb-2 text-sm font-medium">Define a new SLO</h3>
      <div className="flex flex-col gap-2">
        <input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Name" />
        <select aria-label="Metric source" value={metricSource} onChange={(e) => setMetricSource(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          {METRIC_SOURCES.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
        <input placeholder="Target percentage" type="number" min={1} max={100} value={targetPercentage} onChange={(e) => setTargetPercentage(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Target percentage" />
        <input placeholder="Window (days)" type="number" min={1} value={windowDays} onChange={(e) => setWindowDays(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Window (days)" />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button onClick={create} disabled={!name} className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
          Create SLO
        </button>
      </div>
    </div>
  );
}

function IncidentRow({ tenantId, incident, canManage, onChanged }: { tenantId: string; incident: Incident; canManage: boolean; onChanged: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const [timelineOpen, setTimelineOpen] = useState(false);

  const events = useQuery({
    queryKey: ["incident-events", incident.id],
    queryFn: () => api.get<IncidentEvent[]>(`/api/v1/enterprises/${tenantId}/incidents/${incident.id}/events`),
    enabled: timelineOpen,
  });
  const auditTrail = useQuery({
    queryKey: ["incident-audit-trail", incident.id],
    queryFn: () => api.get<CorrelatedAuditEvent[]>(`/api/v1/enterprises/${tenantId}/audit-correlation/incident/${incident.id}`),
    enabled: timelineOpen,
  });

  const acknowledge = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/incidents/${incident.id}/acknowledge`, {});
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to acknowledge incident.");
    }
  };

  const resolve = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/incidents/${incident.id}/resolve`, {});
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to resolve incident.");
    }
  };

  return (
    <li className="rounded-lg border border-zinc-200 px-4 py-2 text-sm dark:border-zinc-800">
      <div className="flex items-center justify-between flex-wrap gap-1">
        <span className="font-medium">{incident.title}</span>
        <span className={incident.severity === "critical" ? "text-red-600" : incident.severity === "warning" ? "text-amber-600" : "text-zinc-500"}>
          {incident.severity}
        </span>
      </div>
      <p className="mt-1 text-xs text-zinc-500">
        {incident.status} &middot; opened {new Date(incident.opened_at).toLocaleString()}
      </p>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="mt-2 flex gap-3 flex-wrap">
        {canManage && incident.status === "open" && <button onClick={acknowledge} className="text-xs underline">Acknowledge</button>}
        {canManage && incident.status !== "resolved" && <button onClick={resolve} className="text-xs text-red-600 underline">Resolve</button>}
        <button onClick={() => setTimelineOpen(!timelineOpen)} className="text-xs underline">
          {timelineOpen ? "Hide timeline" : "Timeline & audit trail"}
        </button>
      </div>
      {timelineOpen && (
        <div className="mt-2 flex flex-col gap-2 rounded border border-zinc-100 p-2 text-xs dark:border-zinc-900">
          <div>
            <p className="mb-1 font-medium">Events</p>
            <ul className="flex flex-col gap-1">
              {events.data?.map((e) => (
                <li key={e.id} className="flex items-center justify-between flex-wrap gap-1">
                  <span>{e.event_type}</span>
                  <span className="text-zinc-500">{new Date(e.created_at).toLocaleString()}</span>
                </li>
              ))}
              {events.data?.length === 0 && <li className="text-zinc-500">No events recorded yet.</li>}
            </ul>
          </div>
          <div>
            <p className="mb-1 font-medium">Audit trail</p>
            <ul className="flex flex-col gap-1">
              {auditTrail.data?.map((e) => (
                <li key={e.id} className="flex items-center justify-between flex-wrap gap-1">
                  <span>{e.action}</span>
                  <span className="text-zinc-500">{new Date(e.occurred_at).toLocaleString()}</span>
                </li>
              ))}
              {auditTrail.data?.length === 0 && <li className="text-zinc-500">No audit events correlated yet.</li>}
            </ul>
          </div>
        </div>
      )}
    </li>
  );
}

function CreateIncidentForm({ tenantId, onCreated }: { tenantId: string; onCreated: () => void }) {
  const [title, setTitle] = useState("");
  const [severity, setSeverity] = useState("warning");
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/incidents`, { title, severity });
      setTitle("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to open incident.");
    }
  };

  return (
    <div className="mt-3 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h3 className="mb-2 text-sm font-medium">Open a new incident</h3>
      <div className="flex flex-col gap-2">
        <input placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Title" />
        <select aria-label="Severity" value={severity} onChange={(e) => setSeverity(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="info">Info</option>
          <option value="warning">Warning</option>
          <option value="critical">Critical</option>
        </select>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button onClick={create} disabled={!title} className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
          Open incident
        </button>
      </div>
    </div>
  );
}

function AlertRuleRow({ tenantId, rule, canManage, onChanged }: { tenantId: string; rule: AlertRule; canManage: boolean; onChanged: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const [lastAlert, setLastAlert] = useState<Alert | null>(null);

  const evaluate = async () => {
    setError(null);
    try {
      const res = await api.post<{ alert: Alert | null }>(`/api/v1/enterprises/${tenantId}/alert-rules/${rule.id}/evaluate`, {});
      setLastAlert(res.alert);
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to evaluate alert rule.");
    }
  };

  const setStatus = async (status: string) => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/alert-rules/${rule.id}/status`, { status });
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update alert rule.");
    }
  };

  return (
    <li className="rounded-lg border border-zinc-200 px-4 py-2 text-sm dark:border-zinc-800">
      <div className="flex items-center justify-between flex-wrap gap-1">
        <span className="font-medium">{rule.name}</span>
        <span className="text-zinc-500">{rule.status}</span>
      </div>
      <p className="mt-1 text-xs text-zinc-500">
        {rule.metric_source} {rule.comparison === "lt" ? "<" : ">"} {rule.threshold}
      </p>
      {lastAlert && <p className="mt-1 text-xs text-red-600">Firing: value {lastAlert.value_at_fire}</p>}
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="mt-2 flex gap-3 flex-wrap">
        <button onClick={evaluate} className="text-xs underline">Evaluate now</button>
        {canManage && (
          <button onClick={() => setStatus(rule.status === "active" ? "paused" : "active")} className="text-xs underline">
            {rule.status === "active" ? "Pause" : "Activate"}
          </button>
        )}
      </div>
    </li>
  );
}

function CreateAlertRuleForm({ tenantId, onCreated }: { tenantId: string; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [metricSource, setMetricSource] = useState(METRIC_SOURCES[0]);
  const [comparison, setComparison] = useState("lt");
  const [threshold, setThreshold] = useState("95");
  const [severity, setSeverity] = useState("warning");
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/alert-rules`, {
        name, metric_source: metricSource, comparison, threshold: Number(threshold), severity,
      });
      setName("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create alert rule.");
    }
  };

  return (
    <div className="mt-3 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h3 className="mb-2 text-sm font-medium">Define a new alert rule</h3>
      <div className="flex flex-col gap-2">
        <input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Name" />
        <select aria-label="Metric source" value={metricSource} onChange={(e) => setMetricSource(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          {METRIC_SOURCES.map((m) => <option key={m} value={m}>{m}</option>)}
          <option value="slo_burn_rate">slo_burn_rate</option>
        </select>
        <div className="flex gap-2 flex-wrap">
          <select aria-label="Comparison operator" value={comparison} onChange={(e) => setComparison(e.target.value)}
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900">
            <option value="lt">below</option>
            <option value="gt">above</option>
          </select>
          <input placeholder="Threshold" type="number" value={threshold} onChange={(e) => setThreshold(e.target.value)}
            className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Threshold" />
        </div>
        <select aria-label="Severity" value={severity} onChange={(e) => setSeverity(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="info">Info</option>
          <option value="warning">Warning</option>
          <option value="critical">Critical</option>
        </select>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button onClick={create} disabled={!name} className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
          Create alert rule
        </button>
      </div>
    </div>
  );
}
