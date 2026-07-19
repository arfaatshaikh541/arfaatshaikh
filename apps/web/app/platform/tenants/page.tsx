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
  // Milestone 4 (hardening): changing a tenant's status is step-up-gated
  // now (core/deps.py:require_platform_step_up) — same pattern the
  // Automation page already uses for approve_action_run.
  const [stepUpTenantId, setStepUpTenantId] = useState<string | null>(null);
  const [stepUpCode, setStepUpCode] = useState("");

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
      // Milestone 4 (hardening): changing a tenant's status is
      // step-up-gated now — `newStatus`/`reason` stay in state so
      // `submitStepUp` can retry with the exact same values once the
      // step-up code is confirmed.
      if (err instanceof ApiError && err.details.step_up_required) {
        setStepUpTenantId(tenantId);
      } else {
        setError(err instanceof ApiError ? err.message : "Something went wrong.");
      }
    } finally {
      setIsBusy(false);
    }
  };

  const submitStepUp = async () => {
    if (!stepUpTenantId) return;
    setError(null);
    setIsBusy(true);
    try {
      await apiClient.post("/api/auth/step-up", { code: stepUpCode });
      setStepUpCode("");
      const tenantId = stepUpTenantId;
      setStepUpTenantId(null);
      await submitStatusChange(tenantId);
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
                  {stepUpTenantId === tenant.id ? (
                    <div className="flex flex-col gap-2 rounded border border-surface-border p-3">
                      <p className="text-sm text-ink-700">
                        Re-confirm your identity with a fresh multi-factor authentication code to continue.
                      </p>
                      <label className="text-xs font-medium text-ink-700" htmlFor={`step-up-${tenant.id}`}>
                        Verification code
                      </label>
                      <input
                        id={`step-up-${tenant.id}`}
                        type="text"
                        inputMode="numeric"
                        value={stepUpCode}
                        onChange={(e) => setStepUpCode(e.target.value)}
                        className="h-9 w-40 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
                      />
                      <div className="flex gap-2">
                        <Button size="sm" isLoading={isBusy} onClick={submitStepUp}>
                          Confirm
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => setStepUpTenantId(null)}>
                          Cancel
                        </Button>
                      </div>
                    </div>
                  ) : null}
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
