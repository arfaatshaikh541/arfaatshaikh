"use client";

import { TENANT_STATUSES, type TenantStatus } from "@gridkeep/security-contracts";
import { Alert, Button, Card, CardHeader, StatusBadge } from "@gridkeep/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { apiClient, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { PlatformTenantSummary } from "@/lib/types";

function statusTone(status: TenantStatus): "neutral" | "positive" | "warning" {
  if (status === "active") return "positive";
  if (status === "read_only" || status === "suspended") return "warning";
  return "neutral";
}

export default function PlatformTenantsPage() {
  const { hasPlatformPermission } = useAuth();
  const canManage = hasPlatformPermission("platform.tenants.manage");
  const queryClient = useQueryClient();

  const [managingTenantId, setManagingTenantId] = useState<string | null>(null);
  const [newStatus, setNewStatus] = useState<TenantStatus>("active");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);

  const tenantsQuery = useQuery({
    queryKey: ["platform", "tenants"],
    queryFn: () => apiClient.get<PlatformTenantSummary[]>("/api/platform/tenants"),
    enabled: canManage,
  });

  if (!canManage) {
    return <p className="text-sm text-ink-500">Not visible to your platform role.</p>;
  }

  const tenants = tenantsQuery.data ?? [];

  const startManaging = (tenant: PlatformTenantSummary) => {
    setManagingTenantId(tenant.id);
    setNewStatus(tenant.status);
    setReason("");
    setError(null);
  };

  const submitStatusChange = async (tenantId: string) => {
    setError(null);
    setIsBusy(true);
    try {
      await apiClient.post(`/api/platform/tenants/${tenantId}/status`, { status: newStatus, reason });
      setManagingTenantId(null);
      queryClient.invalidateQueries({ queryKey: ["platform", "tenants"] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-ink-900">Tenants</h1>
        <p className="text-sm text-ink-500">
          Every workspace on the platform. Changing a tenant&apos;s status is audit-logged and requires a
          reason.
        </p>
      </div>

      {error ? <Alert tone="error">{error}</Alert> : null}

      <Card>
        <CardHeader title={`Tenants (${tenants.length})`} />
        <div className="flex flex-col gap-4">
          {tenants.map((tenant) => (
            <div key={tenant.id} className="rounded border border-surface-border p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-3">
                  <span className="text-sm font-medium text-ink-900">{tenant.name}</span>
                  <span className="text-xs text-ink-500">{tenant.slug}</span>
                  <StatusBadge label={tenant.status.replace(/_/g, " ")} tone={statusTone(tenant.status)} />
                  {tenant.is_demo ? <StatusBadge label="demo" tone="neutral" /> : null}
                </div>
                <Button size="sm" variant="secondary" onClick={() => startManaging(tenant)}>
                  Change status
                </Button>
              </div>

              {managingTenantId === tenant.id ? (
                <div className="mt-3 flex flex-col gap-2 border-t border-surface-border pt-3">
                  <label className="text-xs font-medium text-ink-700" htmlFor={`status-${tenant.id}`}>
                    New status
                  </label>
                  <select
                    id={`status-${tenant.id}`}
                    value={newStatus}
                    onChange={(e) => setNewStatus(e.target.value as TenantStatus)}
                    className="h-9 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
                  >
                    {TENANT_STATUSES.map((status) => (
                      <option key={status} value={status}>
                        {status.replace(/_/g, " ")}
                      </option>
                    ))}
                  </select>
                  <label className="text-xs font-medium text-ink-700" htmlFor={`reason-${tenant.id}`}>
                    Reason
                  </label>
                  <textarea
                    id={`reason-${tenant.id}`}
                    rows={2}
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder="Required — this is written to the audit trail."
                    className="rounded border border-surface-border bg-surface-800 px-3 py-2 text-sm text-ink-900"
                  />
                  <div className="flex gap-2">
                    <Button size="sm" isLoading={isBusy} onClick={() => submitStatusChange(tenant.id)}>
                      Confirm
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setManagingTenantId(null)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
