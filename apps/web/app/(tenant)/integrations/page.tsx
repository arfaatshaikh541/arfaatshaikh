"use client";

import { Banner, Button, Card, TextField } from "@gridkeep/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, api } from "@/lib/api";
import type {
  Integration,
  IntegrationDeliveryListResponse,
  IntegrationListResponse,
} from "@/lib/types";

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  success: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
  failed: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium capitalize ${
        STATUS_STYLES[status] ?? "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
      }`}
    >
      {status}
    </span>
  );
}

function DeliveryHistory({ integrationId }: { integrationId: string }) {
  const deliveriesQuery = useQuery<IntegrationDeliveryListResponse>({
    queryKey: ["integration-deliveries", integrationId],
    queryFn: () => api.get<IntegrationDeliveryListResponse>(`/integrations/${integrationId}/deliveries`),
  });
  const deliveries = deliveriesQuery.data?.deliveries ?? [];

  if (deliveries.length === 0) {
    return <p className="text-sm text-slate-500 dark:text-slate-400">No deliveries yet.</p>;
  }

  return (
    <ul className="flex flex-col gap-2 text-sm">
      {deliveries.map((d) => (
        <li key={d.id} className="flex items-center justify-between rounded-md bg-slate-50 p-2 dark:bg-slate-800/50">
          <div>
            <StatusBadge status={d.status} />
            {d.http_status_code !== null && (
              <span className="ml-2 text-xs text-slate-500 dark:text-slate-400">
                HTTP {d.http_status_code}
              </span>
            )}
            {d.error_message && (
              <p className="mt-1 text-xs text-red-600 dark:text-red-400">{d.error_message}</p>
            )}
          </div>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            {new Date(d.created_at).toLocaleString()} · {d.attempt_count} attempt
            {d.attempt_count === 1 ? "" : "s"}
          </span>
        </li>
      ))}
    </ul>
  );
}

function IntegrationRow({ integration }: { integration: Integration }) {
  const queryClient = useQueryClient();
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["integrations"] });

  const runAction = async (action: string, fn: () => Promise<unknown>) => {
    setError(null);
    setPending(action);
    try {
      await fn();
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : `Could not ${action}.`);
    } finally {
      setPending(null);
    }
  };

  const handleToggleEnabled = () =>
    runAction("update", () =>
      api.patch(`/integrations/${integration.id}`, { enabled: !integration.enabled }),
    );

  const handleDelete = () => {
    if (!window.confirm(`Delete integration "${integration.name}"? This cannot be undone.`)) return;
    runAction("delete", () => api.delete(`/integrations/${integration.id}`));
  };

  return (
    <Card>
      <div className="flex items-center justify-between">
        <div>
          <p className="font-medium">{integration.name}</p>
          <p className="text-sm text-slate-500 dark:text-slate-400">{integration.webhook_url}</p>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              integration.enabled
                ? "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300"
                : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
            }`}
          >
            {integration.enabled ? "Enabled" : "Disabled"}
          </span>
          <Button variant="ghost" isLoading={pending === "update"} onClick={handleToggleEnabled}>
            {integration.enabled ? "Disable" : "Enable"}
          </Button>
          <Button
            variant="ghost"
            onClick={() => setShowHistory((v) => !v)}
          >
            {showHistory ? "Hide history" : "History"}
          </Button>
          <Button variant="ghost" isLoading={pending === "delete"} onClick={handleDelete}>
            Delete
          </Button>
        </div>
      </div>
      {error && <p className="mt-2 text-sm text-red-600 dark:text-red-400">{error}</p>}
      {showHistory && (
        <div className="mt-4 border-t border-slate-200 pt-3 dark:border-slate-800">
          <DeliveryHistory integrationId={integration.id} />
        </div>
      )}
    </Card>
  );
}

export default function IntegrationsPage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [webhookUrl, setWebhookUrl] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const integrationsQuery = useQuery<IntegrationListResponse>({
    queryKey: ["integrations"],
    queryFn: () => api.get<IntegrationListResponse>("/integrations"),
  });

  const handleCreate = async () => {
    if (!name.trim() || !webhookUrl.trim() || webhookSecret.length < 8) return;
    setCreateError(null);
    setCreating(true);
    try {
      await api.post("/integrations", {
        name: name.trim(),
        webhook_url: webhookUrl.trim(),
        webhook_secret: webhookSecret,
      });
      setName("");
      setWebhookUrl("");
      setWebhookSecret("");
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
    } catch (err) {
      setCreateError(err instanceof ApiError ? err.message : "Could not create integration.");
    } finally {
      setCreating(false);
    }
  };

  const integrations = integrationsQuery.data?.integrations ?? [];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Integrations</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Outbound webhooks that leads can be pushed to (e.g. a CRM&apos;s or automation
          platform&apos;s own custom-webhook trigger). Every delivery is signed with your webhook
          secret (<code>X-Gridkeep-Signature</code>, HMAC-SHA256) so your receiver can verify it
          genuinely came from GRIDKEEP.
        </p>
      </div>

      {integrationsQuery.isError && (
        <Banner tone="info">You don&apos;t have permission to view integrations.</Banner>
      )}

      {!integrationsQuery.isError && (
        <>
          <Card>
            <h2 className="text-lg font-medium">Add a webhook</h2>
            {createError && <p className="mt-2 text-sm text-red-600 dark:text-red-400">{createError}</p>}
            <div className="mt-3 flex flex-wrap items-end gap-3">
              <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} />
              <TextField
                label="Webhook URL"
                value={webhookUrl}
                onChange={(e) => setWebhookUrl(e.target.value)}
                placeholder="https://example.com/webhooks/gridkeep"
              />
              <TextField
                label="Secret"
                type="password"
                value={webhookSecret}
                onChange={(e) => setWebhookSecret(e.target.value)}
                placeholder="At least 8 characters"
              />
              <Button
                isLoading={creating}
                disabled={!name.trim() || !webhookUrl.trim() || webhookSecret.length < 8}
                onClick={handleCreate}
              >
                Add integration
              </Button>
            </div>
          </Card>

          <div className="flex flex-col gap-4">
            {integrations.map((integration) => (
              <IntegrationRow key={integration.id} integration={integration} />
            ))}
            {integrations.length === 0 && (
              <Card>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  No integrations yet. Add a webhook above to start pushing leads to it.
                </p>
              </Card>
            )}
          </div>
        </>
      )}
    </div>
  );
}
