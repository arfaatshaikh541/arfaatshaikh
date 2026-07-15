"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Alert, Button, Card, CardHeader, FormRoot, StatusBadge, TextInput } from "@gridkeep/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { apiClient, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { CatalogEntryRead, TenantIntegrationRead } from "@/lib/types";

const schema = z.object({
  label: z.string().min(2, "Give this connection a label.").max(120),
  secret: z.string().min(1, "A credential is required to connect."),
});
type FormValues = z.infer<typeof schema>;

function statusTone(status: string): "positive" | "warning" | "neutral" {
  if (status === "connected") return "positive";
  if (status === "disconnected") return "neutral";
  return "warning";
}

export default function IntegrationsPage() {
  const { hasPermission } = useAuth();
  const queryClient = useQueryClient();
  const canManage = hasPermission("integrations.manage");
  const [connectingProviderId, setConnectingProviderId] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);

  const catalogQuery = useQuery({
    queryKey: ["integrations", "catalog"],
    queryFn: () => apiClient.get<CatalogEntryRead[]>("/api/integrations/catalog"),
  });

  const connectedQuery = useQuery({
    queryKey: ["integrations", "connected"],
    queryFn: () => apiClient.get<TenantIntegrationRead[]>("/api/integrations"),
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const connectedProviderIds = new Set(
    (connectedQuery.data ?? []).filter((ti) => ti.status === "connected").map((ti) => ti.provider_id),
  );

  const startConnect = (providerId: string) => {
    setServerError(null);
    reset();
    setConnectingProviderId(providerId);
  };

  const onConnect = async (values: FormValues) => {
    if (!connectingProviderId) return;
    setServerError(null);
    try {
      await apiClient.post("/api/integrations", { provider_id: connectingProviderId, ...values });
      setConnectingProviderId(null);
      reset();
      queryClient.invalidateQueries({ queryKey: ["integrations"] });
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : "Something went wrong.");
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-ink-900">Integrations</h1>
        <p className="text-sm text-ink-500">
          Connect the tools you already run — GRIDKEEP normalises what they report into a single asset
          graph. Providers marked &ldquo;Simulator&rdquo; return deterministic sample data for evaluation and are
          never presented as real protection.
        </p>
      </div>

      <Card>
        <CardHeader title="Connected" />
        {connectedQuery.data && connectedQuery.data.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-surface-border text-ink-500">
                  <th className="py-2 pr-4 font-medium">Label</th>
                  <th className="py-2 pr-4 font-medium">Provider</th>
                  <th className="py-2 pr-4 font-medium">Status</th>
                  <th className="py-2 pr-4 font-medium">Last synced</th>
                  <th className="py-2 font-medium" />
                </tr>
              </thead>
              <tbody>
                {connectedQuery.data.map((ti) => (
                  <tr key={ti.id} className="border-b border-surface-border/50">
                    <td className="py-2 pr-4 text-ink-900">
                      <Link href={`/integrations/${ti.id}`} className="hover:underline">
                        {ti.label}
                      </Link>
                    </td>
                    <td className="py-2 pr-4 text-ink-500">{ti.provider_name}</td>
                    <td className="py-2 pr-4">
                      <StatusBadge label={ti.status} tone={statusTone(ti.status)} />
                    </td>
                    <td className="py-2 pr-4 text-ink-500">
                      {ti.last_synced_at ? new Date(ti.last_synced_at).toLocaleString() : "Never"}
                    </td>
                    <td className="py-2 text-right">
                      <Link href={`/integrations/${ti.id}`} className="text-sm text-accent hover:underline">
                        Manage
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-ink-500">No integrations connected yet.</p>
        )}
      </Card>

      <Card>
        <CardHeader
          title="Catalogue"
          description={canManage ? undefined : "You don't have permission to connect new integrations."}
        />
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {catalogQuery.data?.map((entry) => {
            const isConnected = connectedProviderIds.has(entry.provider_id);
            return (
              <div key={entry.id} className="flex flex-col gap-3 rounded-md border border-surface-border p-4">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-medium text-ink-900">{entry.name}</p>
                    <p className="text-xs text-ink-500">{entry.category.replace(/_/g, " ")}</p>
                  </div>
                  {entry.is_simulator ? <StatusBadge label="Simulator" tone="warning" /> : null}
                </div>
                <p className="text-sm text-ink-500">{entry.description}</p>
                <div className="flex flex-wrap gap-1">
                  {entry.supported_data_types.map((dt) => (
                    <StatusBadge key={dt} label={dt.replace(/_/g, " ")} />
                  ))}
                </div>
                {isConnected ? (
                  <StatusBadge label="Connected" tone="positive" />
                ) : canManage ? (
                  <Button size="sm" variant="secondary" onClick={() => startConnect(entry.provider_id)}>
                    Connect
                  </Button>
                ) : null}

                {connectingProviderId === entry.provider_id ? (
                  <FormRoot onSubmit={handleSubmit(onConnect)} className="mt-1">
                    {serverError ? <Alert tone="error">{serverError}</Alert> : null}
                    <TextInput
                      label="Label"
                      placeholder={`${entry.name} — Primary`}
                      error={errors.label?.message}
                      {...register("label")}
                    />
                    <div className="flex flex-col gap-1.5">
                      <label htmlFor={`secret-${entry.provider_id}`} className="text-sm font-medium text-ink-700">
                        Credential ({entry.auth_method.replace(/_/g, " ")})
                      </label>
                      <textarea
                        id={`secret-${entry.provider_id}`}
                        rows={3}
                        className="rounded border border-surface-border bg-surface-800 px-3 py-2 text-sm text-ink-900"
                        {...register("secret")}
                      />
                      {errors.secret ? (
                        <p className="text-xs text-severity-critical">{errors.secret.message}</p>
                      ) : null}
                    </div>
                    <div className="flex gap-2">
                      <Button type="submit" size="sm" isLoading={isSubmitting}>
                        Save and connect
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => setConnectingProviderId(null)}
                      >
                        Cancel
                      </Button>
                    </div>
                  </FormRoot>
                ) : null}
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
