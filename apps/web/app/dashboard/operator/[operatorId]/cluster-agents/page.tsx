"use client";

import { use, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api, ApiError, type OperatorMembership } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

interface Cluster {
  id: string;
  name: string;
}

interface ClusterAgent {
  id: string;
  cluster_id: string;
  name: string;
  status: string;
}

interface ClusterAgentCertificate {
  id: string;
  serial_number: string;
  issued_at: string;
  expires_at: string;
  revoked_at?: string;
  revoked_reason?: string;
}

interface ControlMessage {
  id: string;
  direction: string;
  message_type: string;
  status: string;
  received_at: string;
}

interface DeploymentPlanValidation {
  id: string;
  plan_id: string;
  signature_valid: boolean;
  policy_decision: string;
  reason_codes: string[];
  decided_at: string;
}

// Roles known (from docs/security/permission-matrix.md) to hold
// operator.agents.manage -- a UX convenience only, re-checked
// independently by control-api on every request.
const CAN_MANAGE = new Set(["operator_platform_owner", "operator_security_administrator"]);

export default function ClusterAgentsPage({ params }: { params: Promise<{ operatorId: string }> }) {
  const { operatorId } = use(params);
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const members = useQuery({
    queryKey: ["operator-members", operatorId],
    queryFn: () => api.get<OperatorMembership[]>(`/api/v1/operators/${operatorId}/members`),
  });
  const myRole = members.data?.find((m) => m.user_id === user?.user_id)?.role_key ?? "";
  const canManage = CAN_MANAGE.has(myRole);

  const clusters = useQuery({
    queryKey: ["clusters", operatorId],
    queryFn: () => api.get<Cluster[]>(`/api/v1/operators/${operatorId}/clusters`),
  });
  const agents = useQuery({
    queryKey: ["cluster-agents", operatorId],
    queryFn: () => api.get<ClusterAgent[]>(`/api/v1/operators/${operatorId}/cluster-agents`),
  });

  const invalidateAgents = () => queryClient.invalidateQueries({ queryKey: ["cluster-agents", operatorId] });
  const clusterName = (id: string) => clusters.data?.find((c) => c.id === id)?.name ?? id;

  if (members.isError && members.error instanceof ApiError && members.error.status === 403) {
    return (
      <main id="main-content" className="mx-auto w-full max-w-3xl flex-1 p-4 sm:p-8">
        <p>You do not have access to this operator.</p>
        <Link href="/dashboard" className="underline">Back to dashboard</Link>
      </main>
    );
  }

  return (
    <main id="main-content" className="mx-auto w-full max-w-3xl flex-1 p-4 sm:p-8">
      <Link href={`/dashboard/operator/${operatorId}`} className="text-sm underline">&larr; Operator overview</Link>
      <h1 className="mt-2 mb-1 text-2xl font-semibold">Cluster agents</h1>
      <p className="mb-6 text-sm text-zinc-500">
        A cluster agent is a narrower, cluster-scoped identity than an operator agent -- mutually
        authenticated with a certificate from the same platform CA, capable of receiving signed
        deployment-plan validation requests and independently deciding allow/deny before anything
        is ever deployed. There is no real Kubernetes cluster behind this yet (Milestone 7 owns
        actual deployment execution); this exercises the real trust, signing, and replay-protected
        messaging machinery end to end.
      </p>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-medium">Agents</h2>
        <ul className="flex flex-col gap-2">
          {agents.data?.map((a) => (
            <ClusterAgentRow
              key={a.id}
              operatorId={operatorId}
              agent={a}
              clusterName={clusterName(a.cluster_id)}
              canManage={canManage}
              onChanged={invalidateAgents}
            />
          ))}
          {agents.data?.length === 0 && <li className="text-sm text-zinc-500">No cluster agents registered yet.</li>}
        </ul>
      </section>

      {canManage && (
        <RegisterClusterAgentForm operatorId={operatorId} clusters={clusters.data} onRegistered={invalidateAgents} />
      )}
    </main>
  );
}

function ClusterAgentRow({
  operatorId,
  agent,
  clusterName,
  canManage,
  onChanged,
}: {
  operatorId: string;
  agent: ClusterAgent;
  clusterName: string;
  canManage: boolean;
  onChanged: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [namespace, setNamespace] = useState("tenant-workload");

  const certificates = useQuery({
    queryKey: ["cluster-agent-certificates", operatorId, agent.id],
    queryFn: () => api.get<ClusterAgentCertificate[]>(`/api/v1/operators/${operatorId}/cluster-agents/${agent.id}/certificates`),
    enabled: expanded,
  });
  const controlMessages = useQuery({
    queryKey: ["control-messages", operatorId, agent.id],
    queryFn: () => api.get<ControlMessage[]>(`/api/v1/operators/${operatorId}/cluster-agents/${agent.id}/control-messages`),
    enabled: expanded,
  });
  const validations = useQuery({
    queryKey: ["deployment-plan-validations", operatorId, agent.id],
    queryFn: () => api.get<DeploymentPlanValidation[]>(`/api/v1/operators/${operatorId}/cluster-agents/${agent.id}/deployment-plan-validations`),
    enabled: expanded,
  });

  const revoke = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/operators/${operatorId}/cluster-agents/${agent.id}/revoke`, { reason: "revoked from dashboard" });
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to revoke agent.");
    }
  };

  const requestValidation = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/operators/${operatorId}/deployment-plan-requests`, {
        cluster_id: agent.cluster_id,
        namespace,
        resource_quota: { cpu: "4", memory_gb: 16 },
        network_policy: { deny_by_default: true },
        security_context: { run_as_non_root: true },
      });
      controlMessages.refetch();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to request deployment plan validation.");
    }
  };

  return (
    <li className="rounded-lg border border-zinc-200 p-4 text-sm dark:border-zinc-800">
      <button onClick={() => setExpanded(!expanded)} className="flex w-full items-center justify-between text-left">
        <span className="font-medium">{agent.name} <span className="text-zinc-500">({clusterName})</span></span>
        <span className="text-xs text-zinc-500">{agent.status} {expanded ? "−" : "+"}</span>
      </button>

      {expanded && (
        <div className="mt-3 flex flex-col gap-3">
          {error && <p className="text-sm text-red-600">{error}</p>}

          {canManage && agent.status === "active" && (
            <div className="flex items-center gap-2 flex-wrap">
              <input placeholder="Namespace" value={namespace} onChange={(e) => setNamespace(e.target.value)}
                className="rounded-md border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900" aria-label="Namespace" />
              <button onClick={requestValidation} className="rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white dark:bg-white dark:text-zinc-900">
                Request deployment-plan validation
              </button>
              <button onClick={revoke} className="text-xs text-red-600 underline">Revoke</button>
            </div>
          )}

          <div>
            <h4 className="mb-1 text-xs font-medium">Certificates</h4>
            <ul className="flex flex-col gap-1 text-xs text-zinc-500">
              {certificates.data?.map((c) => (
                <li key={c.id}>
                  {c.serial_number} &middot; issued {new Date(c.issued_at).toLocaleString()} &middot;{" "}
                  {c.revoked_at ? `revoked (${c.revoked_reason})` : `expires ${new Date(c.expires_at).toLocaleString()}`}
                </li>
              ))}
              {certificates.data?.length === 0 && <li>No certificates yet.</li>}
            </ul>
          </div>

          <div>
            <h4 className="mb-1 text-xs font-medium">Control messages</h4>
            <ul className="flex flex-col gap-1 text-xs text-zinc-500">
              {controlMessages.data?.map((m) => (
                <li key={m.id}>
                  {m.direction} &middot; {m.message_type} &middot; {m.status} &middot;{" "}
                  {new Date(m.received_at).toLocaleString()}
                </li>
              ))}
              {controlMessages.data?.length === 0 && <li>No control messages yet.</li>}
            </ul>
          </div>

          <div>
            <h4 className="mb-1 text-xs font-medium">Deployment plan validations (local enforcement decisions)</h4>
            <ul className="flex flex-col gap-1 text-xs text-zinc-500">
              {validations.data?.map((v) => (
                <li key={v.id}>
                  {v.plan_id} &middot; {v.policy_decision} &middot; signature valid: {String(v.signature_valid)}
                  {v.reason_codes.length > 0 && ` · ${v.reason_codes.join(", ")}`}
                  {" · "}{new Date(v.decided_at).toLocaleString()}
                </li>
              ))}
              {validations.data?.length === 0 && <li>No validations recorded yet.</li>}
            </ul>
          </div>
        </div>
      )}
    </li>
  );
}

function RegisterClusterAgentForm({
  operatorId,
  clusters,
  onRegistered,
}: {
  operatorId: string;
  clusters: Cluster[] | undefined;
  onRegistered: () => void;
}) {
  const [clusterId, setClusterId] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [justIssued, setJustIssued] = useState<{ agentId: string; token: string } | null>(null);

  const register = async () => {
    setError(null);
    try {
      const result = await api.post<{ agent: ClusterAgent; bootstrap_token: string }>(
        `/api/v1/operators/${operatorId}/cluster-agents`,
        { cluster_id: clusterId, name },
      );
      setJustIssued({ agentId: result.agent.id, token: result.bootstrap_token });
      setName("");
      onRegistered();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to register cluster agent.");
    }
  };

  return (
    <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h3 className="mb-2 text-sm font-medium">Register a new cluster agent</h3>
      <div className="flex flex-col gap-2">
        <select aria-label="Cluster" value={clusterId} onChange={(e) => setClusterId(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">Select a cluster</option>
          {clusters?.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
        <input placeholder="Agent name" value={name} onChange={(e) => setName(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Agent name" />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button onClick={register} disabled={!clusterId || !name}
          className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
          Register cluster agent
        </button>
      </div>

      {justIssued && (
        <div className="mt-4 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm dark:border-amber-800 dark:bg-amber-950">
          <p className="mb-1 font-medium">Bootstrap token (shown once -- copy it now)</p>
          <p className="mb-2 text-xs text-zinc-600 dark:text-zinc-400">
            Agent ID: <code className="rounded bg-white px-1 dark:bg-zinc-900">{justIssued.agentId}</code>. Provide
            this token to the agent (e.g. <code className="rounded bg-white px-1 dark:bg-zinc-900">cmd/mockclusteragent</code>)
            out of band; it cannot be retrieved again.
          </p>
          <code className="block overflow-x-auto rounded bg-white px-2 py-1 dark:bg-zinc-900">{justIssued.token}</code>
        </div>
      )}
    </section>
  );
}
