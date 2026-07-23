"use client";

import { use, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api, ApiError, type OperatorMembership } from "@/lib/api";

interface Deployment {
  id: string;
  cluster_agent_id: string;
  namespace: string;
  replica_count: number;
  status: string;
}

interface DeploymentEvent {
  id: string;
  event_type: string;
  actor_user_id?: string;
  created_at: string;
}

export default function OperatorDeploymentsPage({ params }: { params: Promise<{ operatorId: string }> }) {
  const { operatorId } = use(params);

  const members = useQuery({
    queryKey: ["operator-members", operatorId],
    queryFn: () => api.get<OperatorMembership[]>(`/api/v1/operators/${operatorId}/members`),
  });

  const deployments = useQuery({
    queryKey: ["operator-deployments", operatorId],
    queryFn: () => api.get<Deployment[]>(`/api/v1/operators/${operatorId}/deployments`),
  });

  if (members.isError && members.error instanceof ApiError && members.error.status === 403) {
    return (
      <main className="mx-auto w-full max-w-3xl flex-1 p-8">
        <p>You do not have access to this operator.</p>
        <Link href="/dashboard" className="underline">Back to dashboard</Link>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 p-8">
      <Link href={`/dashboard/operator/${operatorId}`} className="text-sm underline">&larr; Operator overview</Link>
      <h1 className="mt-2 mb-1 text-2xl font-semibold">Deployments</h1>
      <p className="mb-6 text-sm text-zinc-500">
        Every deployment running on this operator&apos;s clusters, reported here read-only --
        deployment execution is driven entirely by the tenant that owns the workload and the
        cluster agent that runs it, over the signed control-message channel; an operator never
        sees the tenant&apos;s workload definition or secret values, only the deployment record
        and its event stream.
      </p>

      <ul className="flex flex-col gap-2">
        {deployments.data?.map((d) => (
          <OperatorDeploymentRow key={d.id} operatorId={operatorId} deployment={d} />
        ))}
        {deployments.data?.length === 0 && <li className="text-sm text-zinc-500">No deployments on this operator&apos;s clusters yet.</li>}
      </ul>
    </main>
  );
}

function OperatorDeploymentRow({ operatorId, deployment }: { operatorId: string; deployment: Deployment }) {
  const [expanded, setExpanded] = useState(false);

  const events = useQuery({
    queryKey: ["operator-deployment-events", operatorId, deployment.id],
    queryFn: () => api.get<DeploymentEvent[]>(`/api/v1/operators/${operatorId}/deployments/${deployment.id}/events`),
    enabled: expanded,
  });

  return (
    <li className="rounded-lg border border-zinc-200 p-4 text-sm dark:border-zinc-800">
      <button onClick={() => setExpanded(!expanded)} className="flex w-full items-center justify-between text-left">
        <span className="font-medium">{deployment.namespace} <span className="text-zinc-500">({deployment.replica_count} replicas)</span></span>
        <span className="text-xs text-zinc-500">{deployment.status} {expanded ? "−" : "+"}</span>
      </button>

      {expanded && (
        <div className="mt-3">
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
      )}
    </li>
  );
}
