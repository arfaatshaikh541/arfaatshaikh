"use client";

import { Alert, Button, Card, CardHeader, StatusBadge } from "@gridkeep/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { apiClient, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type {
  IntegrationHealthRead,
  SyncRunRead,
  TenantIntegrationRead,
  TriggerSyncResponse,
} from "@/lib/types";

function statusTone(status: string): "positive" | "warning" | "neutral" {
  if (status === "connected" || status === "healthy" || status === "success") return "positive";
  if (status === "disconnected") return "neutral";
  return "warning";
}

export default function IntegrationDetailPage() {
  const params = useParams<{ id: string }>();
  const integrationId = params.id;
  const { hasPermission } = useAuth();
  const canManage = hasPermission("integrations.manage");
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [isActing, setIsActing] = useState(false);

  const integrationsQuery = useQuery({
    queryKey: ["integrations", "connected"],
    queryFn: () => apiClient.get<TenantIntegrationRead[]>("/api/integrations"),
  });
  const integration = integrationsQuery.data?.find((ti) => ti.id === integrationId);

  const healthQuery = useQuery({
    queryKey: ["integrations", integrationId, "health"],
    queryFn: () => apiClient.get<IntegrationHealthRead[]>(`/api/integrations/${integrationId}/health`),
    enabled: Boolean(integrationId),
  });

  const syncRunsQuery = useQuery({
    queryKey: ["integrations", integrationId, "sync-runs"],
    queryFn: () => apiClient.get<SyncRunRead[]>(`/api/integrations/${integrationId}/sync-runs`),
    enabled: Boolean(integrationId),
    refetchInterval: 5000,
  });

  const runSync = async () => {
    setActionError(null);
    setActionNotice(null);
    setIsActing(true);
    try {
      const response = await apiClient.post<TriggerSyncResponse>(`/api/integrations/${integrationId}/sync`);
      setActionNotice(`Sync started (run ${response.sync_run_id.slice(0, 8)}).`);
      queryClient.invalidateQueries({ queryKey: ["integrations", integrationId, "sync-runs"] });
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsActing(false);
    }
  };

  const disconnect = async () => {
    setActionError(null);
    setActionNotice(null);
    setIsActing(true);
    try {
      await apiClient.post(`/api/integrations/${integrationId}/disconnect`);
      setActionNotice("Integration disconnected.");
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsActing(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <Link href="/integrations" className="text-sm text-ink-500 hover:underline">
            &larr; Integrations
          </Link>
          <h1 className="mt-1 text-xl font-semibold text-ink-900">{integration?.label ?? "Integration"}</h1>
          {integration ? <p className="text-sm text-ink-500">{integration.provider_name}</p> : null}
        </div>
        {integration ? <StatusBadge label={integration.status} tone={statusTone(integration.status)} /> : null}
      </div>

      {actionError ? <Alert tone="error">{actionError}</Alert> : null}
      {actionNotice ? <Alert tone="success">{actionNotice}</Alert> : null}

      {canManage && integration?.status === "connected" ? (
        <div className="flex gap-2">
          <Button size="sm" onClick={runSync} isLoading={isActing}>
            Sync now
          </Button>
          <Button size="sm" variant="danger" onClick={disconnect} isLoading={isActing}>
            Disconnect
          </Button>
        </div>
      ) : null}

      <Card>
        <CardHeader title="Sync runs" />
        {syncRunsQuery.data && syncRunsQuery.data.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-surface-border text-ink-500">
                  <th className="py-2 pr-4 font-medium">Started</th>
                  <th className="py-2 pr-4 font-medium">Status</th>
                  <th className="py-2 pr-4 font-medium">Processed</th>
                  <th className="py-2 pr-4 font-medium">Created</th>
                  <th className="py-2 pr-4 font-medium">Updated</th>
                  <th className="py-2 font-medium">Error</th>
                </tr>
              </thead>
              <tbody>
                {syncRunsQuery.data.map((run) => (
                  <tr key={run.id} className="border-b border-surface-border/50">
                    <td className="py-2 pr-4 text-ink-700">{new Date(run.started_at).toLocaleString()}</td>
                    <td className="py-2 pr-4">
                      <StatusBadge label={run.status} tone={statusTone(run.status)} />
                    </td>
                    <td className="py-2 pr-4 text-ink-500">{run.records_processed}</td>
                    <td className="py-2 pr-4 text-ink-500">{run.records_created}</td>
                    <td className="py-2 pr-4 text-ink-500">{run.records_updated}</td>
                    <td className="py-2 text-severity-critical">{run.error_message ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-ink-500">No sync runs yet.</p>
        )}
      </Card>

      <Card>
        <CardHeader title="Health history" />
        {healthQuery.data && healthQuery.data.length > 0 ? (
          <ul className="flex flex-col gap-2">
            {healthQuery.data.map((h, idx) => (
              <li key={idx} className="flex items-center justify-between border-b border-surface-border/50 pb-2 text-sm">
                <div>
                  <StatusBadge label={h.status} tone={statusTone(h.status)} />
                  <span className="ml-2 text-ink-700">{h.message}</span>
                </div>
                <span className="text-ink-500">{new Date(h.checked_at).toLocaleString()}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-ink-500">No health checks recorded yet.</p>
        )}
      </Card>
    </div>
  );
}
