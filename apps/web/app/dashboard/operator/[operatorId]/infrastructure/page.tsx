"use client";

import { use, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api, ApiError, type OperatorMembership } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

interface Region {
  id: string;
  key: string;
  name: string;
  jurisdiction_id: string;
  status: string;
}

interface DataCentre {
  id: string;
  region_id: string;
  name: string;
  locality: string;
  status: string;
}

interface Cluster {
  id: string;
  data_centre_id?: string;
  edge_site_id?: string;
  name: string;
  kubernetes_version: string;
  status: string;
}

interface OperatorAgent {
  id: string;
  name: string;
  status: string;
  created_at: string;
}

interface CapacitySnapshot {
  id: string;
  operator_agent_id: string;
  cluster_id: string;
  trust_status: string;
  payload: Record<string, unknown>;
  collected_at: string;
}

// Roles known (from the seeded permission matrix, docs/security/permission-matrix.md)
// to hold the server-side permission each write action requires. This is a UX
// convenience only -- control-api independently re-checks every one of these
// permissions on every request regardless of what this page renders.
const CAN_MANAGE_LOCATIONS = new Set(["operator_platform_owner", "operator_infrastructure_administrator", "operator_cloud_administrator", "operator_edge_administrator"]);
const CAN_MANAGE_CLUSTERS = new Set(["operator_platform_owner", "operator_infrastructure_administrator"]);
const CAN_MANAGE_AGENTS = new Set(["operator_platform_owner", "operator_security_administrator"]);

export default function OperatorInfrastructurePage({ params }: { params: Promise<{ operatorId: string }> }) {
  const { operatorId } = use(params);
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const members = useQuery({
    queryKey: ["operator-members", operatorId],
    queryFn: () => api.get<OperatorMembership[]>(`/api/v1/operators/${operatorId}/members`),
  });
  const myRole = members.data?.find((m) => m.user_id === user?.user_id)?.role_key ?? "";

  const regions = useQuery({
    queryKey: ["regions"],
    queryFn: () => api.get<Region[]>("/api/v1/regions"),
  });
  const dataCentres = useQuery({
    queryKey: ["data-centres", operatorId],
    queryFn: () => api.get<DataCentre[]>(`/api/v1/operators/${operatorId}/data-centres`),
  });
  const clusters = useQuery({
    queryKey: ["clusters", operatorId],
    queryFn: () => api.get<Cluster[]>(`/api/v1/operators/${operatorId}/clusters`),
  });
  const agents = useQuery({
    queryKey: ["agents", operatorId],
    queryFn: () => api.get<OperatorAgent[]>(`/api/v1/operators/${operatorId}/agents`),
  });
  const snapshots = useQuery({
    queryKey: ["capacity-snapshots", operatorId],
    queryFn: () => api.get<CapacitySnapshot[]>(`/api/v1/operators/${operatorId}/capacity-snapshots`),
  });

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
      <h1 className="mt-2 mb-6 text-2xl font-semibold">Infrastructure registry</h1>

      <RegionsSection regions={regions.data} />

      <DataCentresSection
        operatorId={operatorId}
        dataCentres={dataCentres.data}
        regions={regions.data}
        canManage={CAN_MANAGE_LOCATIONS.has(myRole)}
        onCreated={() => queryClient.invalidateQueries({ queryKey: ["data-centres", operatorId] })}
      />

      <ClustersSection
        operatorId={operatorId}
        clusters={clusters.data}
        dataCentres={dataCentres.data}
        canManage={CAN_MANAGE_CLUSTERS.has(myRole)}
        onCreated={() => queryClient.invalidateQueries({ queryKey: ["clusters", operatorId] })}
      />

      <AgentsSection
        operatorId={operatorId}
        agents={agents.data}
        canManage={CAN_MANAGE_AGENTS.has(myRole)}
        onChanged={() => queryClient.invalidateQueries({ queryKey: ["agents", operatorId] })}
      />

      <section>
        <h2 className="mb-3 text-lg font-medium">Capacity snapshots</h2>
        <p className="mb-3 text-xs text-zinc-500">
          Signed facts submitted by operator agents (see the mock connector CLI,
          <code className="mx-1 rounded bg-zinc-100 px-1 dark:bg-zinc-800">cmd/mockconnector</code>
          in Milestone 2) -- every row here already had its signature verified before being stored.
        </p>
        <ul className="flex flex-col gap-2 text-sm">
          {snapshots.data?.map((s) => (
            <li key={s.id} className="rounded-lg border border-zinc-200 px-4 py-2 dark:border-zinc-800">
              <div className="flex items-center justify-between flex-wrap gap-1">
                <span className="font-medium">{clusterName(s.cluster_id)}</span>
                <span className="text-xs text-zinc-500">{s.trust_status} &middot; {new Date(s.collected_at).toLocaleString()}</span>
              </div>
              <pre className="mt-1 overflow-x-auto text-xs text-zinc-500">{JSON.stringify(s.payload)}</pre>
            </li>
          ))}
          {snapshots.data?.length === 0 && <li className="text-zinc-500">No capacity snapshots yet.</li>}
        </ul>
      </section>
    </main>
  );
}

function RegionsSection({ regions }: { regions: Region[] | undefined }) {
  return (
    <section className="mb-8">
      <h2 className="mb-3 text-lg font-medium">Region catalogue</h2>
      <p className="mb-3 text-xs text-zinc-500">
        Platform-curated -- the same taxonomy every operator and enterprise selects from.
      </p>
      <ul className="flex flex-col gap-1 text-sm">
        {regions?.map((r) => (
          <li key={r.id} className="flex justify-between border-b border-zinc-100 py-1 dark:border-zinc-900 flex-wrap gap-1">
            <span>{r.name} ({r.key})</span>
            <span className="text-zinc-500">{r.status}</span>
          </li>
        ))}
        {regions?.length === 0 && <li className="text-zinc-500">No regions defined yet.</li>}
      </ul>
    </section>
  );
}

function DataCentresSection({
  operatorId,
  dataCentres,
  regions,
  canManage,
  onCreated,
}: {
  operatorId: string;
  dataCentres: DataCentre[] | undefined;
  regions: Region[] | undefined;
  canManage: boolean;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [locality, setLocality] = useState("");
  const [regionId, setRegionId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const regionName = (id: string) => regions?.find((r) => r.id === id)?.name ?? id;

  const create = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/operators/${operatorId}/data-centres`, { name, locality, region_id: regionId });
      setName("");
      setLocality("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create data centre.");
    }
  };

  return (
    <section className="mb-8">
      <h2 className="mb-3 text-lg font-medium">Data centres</h2>
      <ul className="flex flex-col gap-2">
        {dataCentres?.map((dc) => (
          <li key={dc.id} className="flex items-center justify-between rounded-lg border border-zinc-200 px-4 py-2 text-sm dark:border-zinc-800 flex-wrap gap-1">
            <span>{dc.name} &middot; {dc.locality} &middot; {regionName(dc.region_id)}</span>
            <span className="text-zinc-500">{dc.status}</span>
          </li>
        ))}
        {dataCentres?.length === 0 && <li className="text-sm text-zinc-500">No data centres yet.</li>}
      </ul>

      {canManage && (
        <div className="mt-4 flex flex-col gap-2 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <h3 className="text-sm font-medium">Add a data centre</h3>
          <input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)}
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Name" />
          <input placeholder="Locality (city)" value={locality} onChange={(e) => setLocality(e.target.value)}
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Locality (city)" />
          <select aria-label="Region" value={regionId} onChange={(e) => setRegionId(e.target.value)}
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900">
            <option value="">Select a region</option>
            {regions?.map((r) => (
              <option key={r.id} value={r.id}>{r.name}</option>
            ))}
          </select>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button onClick={create} disabled={!name || !locality || !regionId}
            className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
            Add data centre
          </button>
        </div>
      )}
    </section>
  );
}

function ClustersSection({
  operatorId,
  clusters,
  dataCentres,
  canManage,
  onCreated,
}: {
  operatorId: string;
  clusters: Cluster[] | undefined;
  dataCentres: DataCentre[] | undefined;
  canManage: boolean;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [k8sVersion, setK8sVersion] = useState("");
  const [dataCentreId, setDataCentreId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    setError(null);
    try {
      await api.post(`/api/v1/operators/${operatorId}/clusters`, {
        name,
        kubernetes_version: k8sVersion,
        data_centre_id: dataCentreId,
      });
      setName("");
      setK8sVersion("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create cluster.");
    }
  };

  return (
    <section className="mb-8">
      <h2 className="mb-3 text-lg font-medium">Clusters</h2>
      <ul className="flex flex-col gap-2">
        {clusters?.map((c) => (
          <li key={c.id} className="flex items-center justify-between rounded-lg border border-zinc-200 px-4 py-2 text-sm dark:border-zinc-800 flex-wrap gap-1">
            <span>{c.name} &middot; k8s {c.kubernetes_version || "unspecified"}</span>
            <span className="text-zinc-500">{c.status}</span>
          </li>
        ))}
        {clusters?.length === 0 && <li className="text-sm text-zinc-500">No clusters yet.</li>}
      </ul>

      {canManage && (
        <div className="mt-4 flex flex-col gap-2 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <h3 className="text-sm font-medium">Add a cluster</h3>
          <input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)}
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Name" />
          <input placeholder="Kubernetes version (e.g. 1.31)" value={k8sVersion} onChange={(e) => setK8sVersion(e.target.value)}
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Kubernetes version (e.g. 1.31)" />
          <select aria-label="Data centre" value={dataCentreId} onChange={(e) => setDataCentreId(e.target.value)}
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900">
            <option value="">Select a data centre</option>
            {dataCentres?.map((dc) => (
              <option key={dc.id} value={dc.id}>{dc.name}</option>
            ))}
          </select>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button onClick={create} disabled={!name || !dataCentreId}
            className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
            Add cluster
          </button>
        </div>
      )}
    </section>
  );
}

function AgentsSection({
  operatorId,
  agents,
  canManage,
  onChanged,
}: {
  operatorId: string;
  agents: OperatorAgent[] | undefined;
  canManage: boolean;
  onChanged: () => void;
}) {
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [justIssued, setJustIssued] = useState<{ agentId: string; token: string } | null>(null);

  const register = async () => {
    setError(null);
    try {
      const result = await api.post<{ agent: OperatorAgent; bootstrap_token: string }>(
        `/api/v1/operators/${operatorId}/agents`,
        { name },
      );
      setJustIssued({ agentId: result.agent.id, token: result.bootstrap_token });
      setName("");
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to register agent.");
    }
  };

  const revoke = async (agentId: string) => {
    try {
      await api.post(`/api/v1/operators/${operatorId}/agents/${agentId}/revoke`, { reason: "revoked from dashboard" });
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to revoke agent.");
    }
  };

  return (
    <section className="mb-8">
      <h2 className="mb-3 text-lg font-medium">Operator agents</h2>
      <ul className="flex flex-col gap-2">
        {agents?.map((a) => (
          <li key={a.id} className="flex items-center justify-between rounded-lg border border-zinc-200 px-4 py-2 text-sm dark:border-zinc-800 flex-wrap gap-1">
            <span>{a.name}</span>
            <span className="flex items-center gap-3 flex-wrap">
              <span className="text-zinc-500">{a.status}</span>
              {canManage && a.status !== "revoked" && (
                <button onClick={() => revoke(a.id)} className="text-xs text-red-600 underline">
                  Revoke
                </button>
              )}
            </span>
          </li>
        ))}
        {agents?.length === 0 && <li className="text-sm text-zinc-500">No agents registered yet.</li>}
      </ul>

      {justIssued && (
        <div className="mt-4 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm dark:border-amber-800 dark:bg-amber-950">
          <p className="mb-1 font-medium">Bootstrap token (shown once -- copy it now)</p>
          <p className="mb-2 text-xs text-zinc-600 dark:text-zinc-400">
            Agent ID: <code className="rounded bg-white px-1 dark:bg-zinc-900">{justIssued.agentId}</code>. Provide
            this token to the agent out of band; it cannot be retrieved again.
          </p>
          <code className="block overflow-x-auto rounded bg-white px-2 py-1 dark:bg-zinc-900">{justIssued.token}</code>
        </div>
      )}

      {canManage && (
        <div className="mt-4 flex flex-col gap-2 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
          <h3 className="text-sm font-medium">Register a new agent</h3>
          <input placeholder="Agent name" value={name} onChange={(e) => setName(e.target.value)}
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900" aria-label="Agent name" />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button onClick={register} disabled={!name}
            className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-zinc-900">
            Register agent
          </button>
        </div>
      )}
    </section>
  );
}
