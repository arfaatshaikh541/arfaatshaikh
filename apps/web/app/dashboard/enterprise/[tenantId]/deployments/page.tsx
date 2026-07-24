"use client";

import { use, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api, ApiError, type EnterpriseMembership } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

interface Deployment {
  id: string;
  cluster_agent_id: string;
  workload_version_id: string;
  capacity_reservation_id: string;
  namespace: string;
  replica_count: number;
  status: string;
}

interface DeploymentPlan {
  id: string;
  version: number;
  status: string;
  manifest_hash: string;
  signature?: string;
  requested_by: string;
  approved_by?: string;
  rejected_reason?: string;
}

interface DeploymentEvent {
  id: string;
  event_type: string;
  detail: Record<string, unknown>;
  actor_user_id?: string;
  created_at: string;
}

interface Reservation {
  id: string;
  capacity_offer_id: string;
  quantity: number;
  status: string;
}

interface WorkloadSecret {
  id: string;
  key: string;
  created_at: string;
}

// RedactedAttestationResult is the "customer verification view" -- it
// deliberately has no field for reported measurements or raw evidence;
// control-api's own query never selects those columns for this endpoint.
interface RedactedAttestationResult {
  id: string;
  provider_type: string;
  decision: string;
  reason_codes: string[];
  evaluated_at: string;
}

// Roles known (from docs/security/permission-matrix.md) to hold the
// server-side permission each action requires -- a UX convenience only,
// re-checked independently by control-api on every request.
const CAN_DEPLOY = new Set(["enterprise_owner", "enterprise_admin", "ai_platform_engineer", "application_owner", "devops_engineer"]);
const CAN_APPROVE = new Set(["enterprise_owner", "enterprise_admin"]);
const CAN_SCALE = new Set(["enterprise_owner", "enterprise_admin", "ai_platform_engineer", "application_owner", "devops_engineer"]);
const CAN_PAUSE = new Set(["enterprise_owner", "enterprise_admin", "application_owner", "devops_engineer"]);
const CAN_TERMINATE = new Set(["enterprise_owner", "enterprise_admin", "devops_engineer", "security_administrator"]);
const CAN_RETRY = new Set(["enterprise_owner", "enterprise_admin", "devops_engineer"]);
const CAN_ROLLBACK = new Set(["enterprise_owner", "enterprise_admin", "ai_platform_engineer", "devops_engineer"]);
const CAN_MANAGE_SECRETS = new Set(["enterprise_owner", "enterprise_admin", "security_administrator"]);
const CAN_VIEW_ATTESTATION = new Set([
  "enterprise_owner", "enterprise_admin", "ai_platform_engineer", "application_owner",
  "devops_engineer", "read_only_auditor", "compliance_manager", "security_administrator",
]);

export default function DeploymentsPage({ params }: { params: Promise<{ tenantId: string }> }) {
  const { tenantId } = use(params);
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const members = useQuery({
    queryKey: ["tenant-members", tenantId],
    queryFn: () => api.get<EnterpriseMembership[]>(`/api/v1/enterprises/${tenantId}/members`),
  });
  const myRole = members.data?.find((m) => m.user_id === user?.user_id)?.role_key ?? "";
  const perms = {
    deploy: CAN_DEPLOY.has(myRole),
    approve: CAN_APPROVE.has(myRole),
    scale: CAN_SCALE.has(myRole),
    pause: CAN_PAUSE.has(myRole),
    terminate: CAN_TERMINATE.has(myRole),
    retry: CAN_RETRY.has(myRole),
    rollback: CAN_ROLLBACK.has(myRole),
    manageSecrets: CAN_MANAGE_SECRETS.has(myRole),
    viewAttestation: CAN_VIEW_ATTESTATION.has(myRole),
  };

  const deployments = useQuery({
    queryKey: ["deployments", tenantId],
    queryFn: () => api.get<Deployment[]>(`/api/v1/enterprises/${tenantId}/deployments`),
  });
  const reservations = useQuery({
    queryKey: ["deployments-reservations", tenantId],
    queryFn: () => api.get<Reservation[]>(`/api/v1/enterprises/${tenantId}/capacity-reservations`),
  });

  const invalidateDeployments = () => queryClient.invalidateQueries({ queryKey: ["deployments", tenantId] });

  const deployableReservations = (reservations.data ?? []).filter(
    (r) => r.status === "committed" && !deployments.data?.some((d) => d.capacity_reservation_id === r.id),
  );

  if (members.isError && members.error instanceof ApiError && members.error.status === 403) {
    return (
      <main id="main-content" className="mx-auto w-full max-w-3xl flex-1 p-4 sm:p-8">
        <p>You do not have access to this tenant&apos;s deployments.</p>
        <Link href="/dashboard" className="underline">Back to dashboard</Link>
      </main>
    );
  }

  return (
    <main id="main-content" className="mx-auto w-full max-w-3xl flex-1 p-4 sm:p-8">
      <Link href={`/dashboard/enterprise/${tenantId}`} className="text-sm underline"><span aria-hidden="true" className="rtl-mirror">&larr;</span> Tenant overview</Link>
      <h1 className="mt-2 mb-1 text-2xl font-semibold">Deployments</h1>
      <p className="mb-6 text-sm text-zinc-500">
        A deployment turns a committed capacity reservation into a signed, dual-control-approved
        plan sent to the operator&apos;s cluster agent over the same signed, replay-protected
        control-message channel Milestone 6 established. No plan is ever executed until a
        genuinely different user than whoever drafted it has approved it, and every state
        transition below -- whether you triggered it or the cluster agent reported it -- is
        recorded in that deployment&apos;s append-only event stream.
      </p>

      {perms.deploy && (
        <CreateDeploymentForm
          tenantId={tenantId}
          reservations={deployableReservations}
          onCreated={invalidateDeployments}
        />
      )}

      <section className="mt-8">
        <h2 className="mb-3 text-lg font-medium">Your deployments</h2>
        <ul className="flex flex-col gap-2">
          {deployments.data?.map((d) => (
            <DeploymentRow key={d.id} tenantId={tenantId} deployment={d} perms={perms} onChanged={invalidateDeployments} />
          ))}
          {deployments.data?.length === 0 && <li className="text-sm text-zinc-500">No deployments yet.</li>}
        </ul>
      </section>

      {perms.manageSecrets && <WorkloadSecretsSection tenantId={tenantId} />}
    </main>
  );
}

function CreateDeploymentForm({
  tenantId,
  reservations,
  onCreated,
}: {
  tenantId: string;
  reservations: Reservation[];
  onCreated: () => void;
}) {
  const [reservationId, setReservationId] = useState("");
  const [namespace, setNamespace] = useState("");
  const [replicaCount, setReplicaCount] = useState("1");
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/deployments`, {
        capacity_reservation_id: reservationId,
        namespace,
        replica_count: Number(replicaCount),
      });
      setReservationId("");
      setNamespace("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create deployment.");
    }
  };

  return (
    <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h3 className="mb-2 text-sm font-medium">Create a deployment from a committed reservation</h3>
      <div className="flex flex-col gap-2">
        <select aria-label="Capacity reservation" value={reservationId} onChange={(e) => setReservationId(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">Select a committed, not-yet-deployed reservation</option>
          {reservations.map((r) => (
            <option key={r.id} value={r.id}>{r.id} ({r.quantity} unit(s))</option>
          ))}
        </select>
        <input placeholder="Namespace" value={namespace} onChange={(e) => setNamespace(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Namespace" />
        <input placeholder="Replica count" type="number" min={1} value={replicaCount} onChange={(e) => setReplicaCount(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Replica count" />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button onClick={create} disabled={!reservationId || !namespace}
          className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
          Create deployment
        </button>
      </div>
    </section>
  );
}

interface Perms {
  deploy: boolean;
  approve: boolean;
  scale: boolean;
  pause: boolean;
  terminate: boolean;
  retry: boolean;
  rollback: boolean;
  manageSecrets: boolean;
  viewAttestation: boolean;
}

function DeploymentRow({
  tenantId,
  deployment,
  perms,
  onChanged,
}: {
  tenantId: string;
  deployment: Deployment;
  perms: Perms;
  onChanged: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [replicaCount, setReplicaCount] = useState("2");
  const [rollbackVersion, setRollbackVersion] = useState("1");
  const { user } = useAuth();

  const plans = useQuery({
    queryKey: ["deployment-plans", tenantId, deployment.id],
    queryFn: () => api.get<DeploymentPlan[]>(`/api/v1/enterprises/${tenantId}/deployments/${deployment.id}/plans`),
    enabled: expanded,
  });
  const events = useQuery({
    queryKey: ["deployment-events", tenantId, deployment.id],
    queryFn: () => api.get<DeploymentEvent[]>(`/api/v1/enterprises/${tenantId}/deployments/${deployment.id}/events`),
    enabled: expanded,
  });
  const attestationResults = useQuery({
    queryKey: ["deployment-attestation-results", tenantId, deployment.id],
    queryFn: () => api.get<RedactedAttestationResult[]>(`/api/v1/enterprises/${tenantId}/deployments/${deployment.id}/attestation-results`),
    enabled: expanded && perms.viewAttestation,
  });

  const refresh = () => {
    plans.refetch();
    events.refetch();
    onChanged();
  };

  const run = async (action: () => Promise<unknown>) => {
    setError(null);
    try {
      await action();
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Action failed.");
    }
  };

  const draftPlan = () => run(() => api.post(`/api/v1/enterprises/${tenantId}/deployments/${deployment.id}/plans`, {}));
  const requestApproval = (planId: string) =>
    run(() => api.post(`/api/v1/enterprises/${tenantId}/deployments/${deployment.id}/plans/${planId}/request-approval`, {}));
  const approvePlan = (planId: string) =>
    run(() => api.post(`/api/v1/enterprises/${tenantId}/deployments/${deployment.id}/plans/${planId}/approve`, {}));
  const rejectPlan = (planId: string) =>
    run(() => api.post(`/api/v1/enterprises/${tenantId}/deployments/${deployment.id}/plans/${planId}/reject`, { reason: "rejected from dashboard" }));
  const submitPlan = (planId: string) =>
    run(() => api.post(`/api/v1/enterprises/${tenantId}/deployments/${deployment.id}/plans/${planId}/submit`, {}));
  const scale = () => run(() => api.post(`/api/v1/enterprises/${tenantId}/deployments/${deployment.id}/scale`, { replica_count: Number(replicaCount) }));
  const pause = () => run(() => api.post(`/api/v1/enterprises/${tenantId}/deployments/${deployment.id}/pause`, {}));
  const resume = () => run(() => api.post(`/api/v1/enterprises/${tenantId}/deployments/${deployment.id}/resume`, {}));
  const terminate = () => run(() => api.post(`/api/v1/enterprises/${tenantId}/deployments/${deployment.id}/terminate`, {}));
  const retry = () => run(() => api.post(`/api/v1/enterprises/${tenantId}/deployments/${deployment.id}/retry`, {}));
  const rollback = () => run(() => api.post(`/api/v1/enterprises/${tenantId}/deployments/${deployment.id}/rollback`, { target_version: Number(rollbackVersion) }));

  const latestPlan = plans.data?.slice().sort((a, b) => b.version - a.version)[0];

  return (
    <li className="rounded-lg border border-zinc-200 p-4 text-sm dark:border-zinc-800">
      <button onClick={() => setExpanded(!expanded)} className="flex w-full items-center justify-between text-start">
        <span className="font-medium">{deployment.namespace} <span className="text-zinc-500">({deployment.replica_count} replicas)</span></span>
        <span className="text-xs text-zinc-500">{deployment.status} {expanded ? "−" : "+"}</span>
      </button>

      {expanded && (
        <div className="mt-3 flex flex-col gap-4">
          {error && <p className="text-sm text-red-600">{error}</p>}

          <div>
            <div className="mb-1 flex items-center justify-between flex-wrap gap-1">
              <h4 className="text-xs font-medium">Deployment plans</h4>
              {perms.deploy && deployment.status === "pending_plan_approval" && !latestPlan && (
                <button onClick={draftPlan} className="text-xs underline">Draft a plan</button>
              )}
            </div>
            <ul className="flex flex-col gap-1 text-xs text-zinc-500">
              {plans.data?.slice().sort((a, b) => b.version - a.version).map((p) => (
                <li key={p.id} className="rounded border border-zinc-100 p-2 dark:border-zinc-900">
                  <div className="flex items-center justify-between flex-wrap gap-1">
                    <span>v{p.version} &middot; {p.manifest_hash.slice(0, 12)}&hellip;</span>
                    <span>{p.status}</span>
                  </div>
                  {p.rejected_reason && <p className="mt-1">Rejected: {p.rejected_reason}</p>}
                  <div className="mt-1 flex gap-3 flex-wrap">
                    {perms.deploy && p.status === "draft" && (
                      <button onClick={() => requestApproval(p.id)} className="underline">Request approval</button>
                    )}
                    {perms.approve && p.status === "pending_approval" && p.requested_by !== user?.user_id && (
                      <>
                        <button onClick={() => approvePlan(p.id)} className="underline">Approve</button>
                        <button onClick={() => rejectPlan(p.id)} className="text-red-600 underline">Reject</button>
                      </>
                    )}
                    {perms.approve && p.status === "pending_approval" && p.requested_by === user?.user_id && (
                      <span>Awaiting a different approver</span>
                    )}
                    {perms.deploy && p.status === "approved" && (
                      <button onClick={() => submitPlan(p.id)} className="underline">Submit for execution</button>
                    )}
                  </div>
                </li>
              ))}
              {plans.data?.length === 0 && <li>No plans drafted yet.</li>}
            </ul>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {perms.scale && deployment.status === "running" && (
              <span className="flex items-center gap-1 flex-wrap">
                <input type="number" min={1} value={replicaCount} onChange={(e) => setReplicaCount(e.target.value)}
                  aria-label="Replica count" className="w-16 rounded-md border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900" />
                <button onClick={scale} className="text-xs underline">Scale</button>
              </span>
            )}
            {perms.pause && deployment.status === "running" && (
              <button onClick={pause} className="text-xs underline">Pause</button>
            )}
            {perms.pause && deployment.status === "paused" && (
              <button onClick={resume} className="text-xs underline">Resume</button>
            )}
            {perms.rollback && (
              <span className="flex items-center gap-1 flex-wrap">
                <input type="number" min={1} value={rollbackVersion} onChange={(e) => setRollbackVersion(e.target.value)}
                  aria-label="Rollback target version" className="w-16 rounded-md border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900" />
                <button onClick={rollback} className="text-xs underline">Roll back to version</button>
              </span>
            )}
            {perms.retry && deployment.status === "failed" && (
              <button onClick={retry} className="text-xs underline">Retry</button>
            )}
            {perms.terminate && deployment.status !== "terminated" && deployment.status !== "terminating" && (
              <button onClick={terminate} className="text-xs text-red-600 underline">Terminate</button>
            )}
          </div>

          <div>
            <h4 className="mb-1 text-xs font-medium">Event stream</h4>
            <ul className="flex flex-col gap-1 text-xs text-zinc-500">
              {events.data?.map((e) => (
                <li key={e.id}>
                  {new Date(e.created_at).toLocaleString()} &middot; {e.event_type}
                  {e.actor_user_id ? "" : " (reported by cluster agent)"}
                </li>
              ))}
              {events.data?.length === 0 && <li>No events yet.</li>}
            </ul>
          </div>

          {perms.viewAttestation && (
            <div>
              <h4 className="mb-1 text-xs font-medium">Confidential-computing attestation</h4>
              <p className="mb-1 text-xs text-zinc-500">
                Verified by control-api against the operator&apos;s cluster hardware policy --
                this view never shows raw evidence or reported measurements, only the decision.
              </p>
              <ul className="flex flex-col gap-1 text-xs text-zinc-500">
                {attestationResults.data?.map((r) => (
                  <li key={r.id}>
                    {new Date(r.evaluated_at).toLocaleString()} &middot; {r.provider_type} &middot;{" "}
                    <span className={r.decision === "pass" ? "text-emerald-600" : "text-red-600"}>{r.decision}</span>
                    {r.reason_codes.length > 0 && ` · ${r.reason_codes.join(", ")}`}
                  </li>
                ))}
                {attestationResults.data?.length === 0 && <li>No attestation evidence submitted yet.</li>}
              </ul>
            </div>
          )}
        </div>
      )}
    </li>
  );
}

function WorkloadSecretsSection({ tenantId }: { tenantId: string }) {
  const [versionId, setVersionId] = useState("");
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const secrets = useQuery({
    queryKey: ["workload-secrets", tenantId, versionId],
    queryFn: () => api.get<WorkloadSecret[]>(`/api/v1/enterprises/${tenantId}/workload-versions/${versionId}/secrets`),
    enabled: !!versionId,
  });

  const invalidateSecrets = () => queryClient.invalidateQueries({ queryKey: ["workload-secrets", tenantId, versionId] });

  const create = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/workload-versions/${versionId}/secrets`, { key, value });
      setKey("");
      setValue("");
      invalidateSecrets();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create secret.");
    }
  };

  const remove = async (secretId: string) => {
    setError(null);
    try {
      await api.delete(`/api/v1/enterprises/${tenantId}/workload-versions/${versionId}/secrets/${secretId}`);
      invalidateSecrets();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete secret.");
    }
  };

  return (
    <section className="mt-8">
      <h2 className="mb-1 text-lg font-medium">Workload secrets</h2>
      <p className="mb-3 text-xs text-zinc-500">
        Values are encrypted at rest and never returned by this or any other API response --
        only key names and metadata. A deployed workload&apos;s cluster agent fetches decrypted
        values itself, over a separate certificate-authenticated channel, only for the
        deployment it is actually running.
      </p>
      <input placeholder="Workload version ID" value={versionId} onChange={(e) => setVersionId(e.target.value)}
        className="mb-2 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Workload version ID" />
      <ul className="mb-3 flex flex-col gap-1 text-xs text-zinc-500">
        {secrets.data?.map((s) => (
          <li key={s.id} className="flex items-center justify-between rounded border border-zinc-100 px-2 py-1 dark:border-zinc-900 flex-wrap gap-1">
            <span>{s.key}</span>
            <button onClick={() => remove(s.id)} className="text-red-600 underline">Delete</button>
          </li>
        ))}
        {versionId && secrets.data?.length === 0 && <li>No secrets set for this workload version.</li>}
      </ul>
      {versionId && (
        <div className="flex flex-col gap-2 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <input placeholder="Key (e.g. API_KEY)" value={key} onChange={(e) => setKey(e.target.value.toUpperCase())}
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Key (e.g. API_KEY)" />
          <input placeholder="Value" type="password" value={value} onChange={(e) => setValue(e.target.value)}
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Value" />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button onClick={create} disabled={!key || !value}
            className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
            Add secret
          </button>
        </div>
      )}
    </section>
  );
}
