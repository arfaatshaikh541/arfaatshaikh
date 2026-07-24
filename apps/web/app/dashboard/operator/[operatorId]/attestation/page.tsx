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

interface AttestationPolicy {
  id: string;
  cluster_id: string;
  provider_type: string;
  expected_measurements: Record<string, unknown>;
  status: string;
  revoked_reason?: string;
  created_at: string;
}

interface AttestationResult {
  id: string;
  deployment_id: string;
  provider_type: string;
  measurements: Record<string, unknown>;
  raw_evidence: string;
  decision: string;
  reason_codes: string[];
  evaluated_at: string;
}

// Roles known (from docs/security/permission-matrix.md) to hold
// operator.attestation.manage -- a UX convenience only, re-checked
// independently by control-api on every request.
const CAN_MANAGE = new Set(["operator_platform_owner", "operator_security_administrator"]);

export default function AttestationPage({ params }: { params: Promise<{ operatorId: string }> }) {
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
  const clusterAgents = useQuery({
    queryKey: ["cluster-agents", operatorId],
    queryFn: () => api.get<ClusterAgent[]>(`/api/v1/operators/${operatorId}/cluster-agents`),
  });
  const policies = useQuery({
    queryKey: ["attestation-policies", operatorId],
    queryFn: () => api.get<AttestationPolicy[]>(`/api/v1/operators/${operatorId}/attestation-policies`),
  });

  const invalidatePolicies = () => queryClient.invalidateQueries({ queryKey: ["attestation-policies", operatorId] });
  const clusterName = (id: string) => clusters.data?.find((c) => c.id === id)?.name ?? id;
  const agentForCluster = (clusterId: string) => clusterAgents.data?.find((a) => a.cluster_id === clusterId);

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
      <h1 className="mt-2 mb-1 text-2xl font-semibold">Confidential-computing attestation</h1>
      <p className="mb-6 text-sm text-zinc-500">
        An attestation policy declares what a confidential-computing-capable cluster&apos;s
        hardware is expected to report -- control-api verifies every piece of evidence a cluster
        agent submits against it before releasing any workload secret for a deployment that
        requires confidential computing. This environment uses a clearly-labelled mock provider
        only; it makes no claim of verifying genuine AMD SEV-SNP/Intel TDX/NVIDIA
        confidential-computing hardware.
      </p>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-medium">Attestation policies</h2>
        <ul className="flex flex-col gap-2">
          {policies.data?.map((p) => (
            <PolicyRow
              key={p.id}
              operatorId={operatorId}
              policy={p}
              clusterName={clusterName(p.cluster_id)}
              agent={agentForCluster(p.cluster_id)}
              canManage={canManage}
              onChanged={invalidatePolicies}
            />
          ))}
          {policies.data?.length === 0 && <li className="text-sm text-zinc-500">No attestation policies configured yet.</li>}
        </ul>
      </section>

      {canManage && (
        <CreatePolicyForm operatorId={operatorId} clusters={clusters.data} onCreated={invalidatePolicies} />
      )}
    </main>
  );
}

function PolicyRow({
  operatorId,
  policy,
  clusterName,
  agent,
  canManage,
  onChanged,
}: {
  operatorId: string;
  policy: AttestationPolicy;
  clusterName: string;
  agent: ClusterAgent | undefined;
  canManage: boolean;
  onChanged: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const results = useQuery({
    queryKey: ["attestation-results", operatorId, agent?.id],
    queryFn: () => api.get<AttestationResult[]>(`/api/v1/operators/${operatorId}/cluster-agents/${agent!.id}/attestation-results`),
    enabled: expanded && !!agent,
  });

  const revoke = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/operators/${operatorId}/attestation-policies/${policy.id}/revoke`, { reason: "revoked from dashboard" });
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to revoke policy.");
    }
  };

  return (
    <li className="rounded-lg border border-zinc-200 p-4 text-sm dark:border-zinc-800">
      <button onClick={() => setExpanded(!expanded)} className="flex w-full items-center justify-between text-left">
        <span className="font-medium">{clusterName} <span className="text-zinc-500">({policy.provider_type})</span></span>
        <span className="text-xs text-zinc-500">{policy.status} {expanded ? "−" : "+"}</span>
      </button>

      {expanded && (
        <div className="mt-3 flex flex-col gap-3">
          {error && <p className="text-red-600">{error}</p>}
          {policy.revoked_reason && <p className="text-xs text-zinc-500">Revoked: {policy.revoked_reason}</p>}

          <div>
            <h4 className="mb-1 text-xs font-medium">Expected measurements</h4>
            <pre className="overflow-x-auto rounded bg-zinc-50 p-2 text-xs dark:bg-zinc-900">
              {JSON.stringify(policy.expected_measurements, null, 2)}
            </pre>
          </div>

          {canManage && policy.status === "active" && (
            <button onClick={revoke} className="self-start text-xs text-red-600 underline">Revoke</button>
          )}

          {agent && (
            <div>
              <h4 className="mb-1 text-xs font-medium">Attestation results for {agent.name}</h4>
              <ul className="flex flex-col gap-1 text-xs text-zinc-500">
                {results.data?.map((r) => (
                  <li key={r.id} className="rounded border border-zinc-100 p-2 dark:border-zinc-900">
                    <div className="flex items-center justify-between flex-wrap gap-1">
                      <span>{new Date(r.evaluated_at).toLocaleString()}</span>
                      <span className={r.decision === "pass" ? "text-emerald-600" : "text-red-600"}>{r.decision}</span>
                    </div>
                    {r.reason_codes.length > 0 && <p>Reasons: {r.reason_codes.join(", ")}</p>}
                    <p>Deployment: {r.deployment_id}</p>
                    <details className="mt-1">
                      <summary className="cursor-pointer">Measurements &amp; raw evidence</summary>
                      <pre className="mt-1 overflow-x-auto rounded bg-zinc-50 p-2 dark:bg-zinc-950">
                        {JSON.stringify(r.measurements, null, 2)}
                        {"\n"}
                        {r.raw_evidence}
                      </pre>
                    </details>
                  </li>
                ))}
                {results.data?.length === 0 && <li>No attestation evidence submitted yet.</li>}
              </ul>
            </div>
          )}
        </div>
      )}
    </li>
  );
}

function CreatePolicyForm({
  operatorId,
  clusters,
  onCreated,
}: {
  operatorId: string;
  clusters: Cluster[] | undefined;
  onCreated: () => void;
}) {
  const [clusterId, setClusterId] = useState("");
  const [providerType, setProviderType] = useState("mock");
  const [measurementsText, setMeasurementsText] = useState('{\n  "platform": "mock-tee-v1",\n  "firmware_hash": "abc123"\n}');
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    setError(null);
    let expectedMeasurements: Record<string, unknown>;
    try {
      expectedMeasurements = JSON.parse(measurementsText);
    } catch {
      setError("Expected measurements must be valid JSON.");
      return;
    }
    try {
      await api.post(`/api/v1/operators/${operatorId}/attestation-policies`, {
        cluster_id: clusterId, provider_type: providerType, expected_measurements: expectedMeasurements,
      });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create attestation policy.");
    }
  };

  return (
    <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h3 className="mb-2 text-sm font-medium">Configure an attestation policy</h3>
      <p className="mb-2 text-xs text-zinc-500">
        Creating a new policy for a cluster that already has an active one supersedes it -- the
        previous policy is automatically revoked, not edited in place.
      </p>
      <div className="flex flex-col gap-2">
        <select aria-label="Cluster" value={clusterId} onChange={(e) => setClusterId(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">Select a cluster</option>
          {clusters?.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
        <select aria-label="Attestation provider type" value={providerType} onChange={(e) => setProviderType(e.target.value)}
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900">
          <option value="mock">mock (local development)</option>
          <option value="amd_sev_snp">AMD SEV-SNP (not yet implemented)</option>
          <option value="intel_tdx">Intel TDX (not yet implemented)</option>
          <option value="nvidia_cc">NVIDIA confidential computing (not yet implemented)</option>
          <option value="cloud_confidential_vm">Cloud confidential VM (not yet implemented)</option>
          <option value="hsm">HSM-backed (not yet implemented)</option>
        </select>
        <textarea value={measurementsText} onChange={(e) => setMeasurementsText(e.target.value)} rows={6}
          className="rounded-md border border-zinc-300 px-3 py-2 font-mono text-xs dark:border-zinc-700 dark:bg-zinc-900" />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button onClick={create} disabled={!clusterId}
          className="self-start rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
          Create policy
        </button>
      </div>
    </section>
  );
}
