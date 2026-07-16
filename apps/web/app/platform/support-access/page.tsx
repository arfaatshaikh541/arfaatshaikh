"use client";

import { Alert, Button, Card, CardHeader, StatusBadge } from "@gridkeep/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { apiClient, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { PlatformTenantSummary, SupportAccessGrantRead } from "@/lib/types";

function statusTone(status: string): "neutral" | "positive" | "warning" {
  if (status === "active") return "positive";
  if (status === "pending") return "warning";
  return "neutral";
}

export default function PlatformSupportAccessPage() {
  const { me, hasPlatformPermission } = useAuth();
  const canRequest = hasPlatformPermission("platform.support_access");
  const queryClient = useQueryClient();
  const router = useRouter();

  const [statusFilter, setStatusFilter] = useState<string>("");
  const [showRequestForm, setShowRequestForm] = useState(false);
  const [tenantId, setTenantId] = useState("");
  const [reason, setReason] = useState("");
  const [durationHours, setDurationHours] = useState(4);
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);

  const tenantsQuery = useQuery({
    queryKey: ["platform", "tenants"],
    queryFn: () => apiClient.get<PlatformTenantSummary[]>("/api/platform/tenants"),
    enabled: canRequest,
  });

  const grantsQuery = useQuery({
    queryKey: ["platform", "support-access-grants", statusFilter],
    queryFn: () =>
      apiClient.get<SupportAccessGrantRead[]>("/api/platform/support-access-grants", {
        ...(statusFilter ? { status: statusFilter } : {}),
      }),
    enabled: canRequest,
  });

  if (!canRequest) {
    return <p className="text-sm text-ink-500">Not visible to your platform role.</p>;
  }

  const tenants = tenantsQuery.data ?? [];
  const grants = grantsQuery.data ?? [];
  const tenantName = (id: string) => tenants.find((t) => t.id === id)?.name ?? id;

  const submitRequest = async () => {
    setError(null);
    setIsBusy(true);
    try {
      await apiClient.post("/api/platform/support-access-grants", {
        tenant_id: tenantId,
        reason,
        duration_hours: durationHours,
      });
      setShowRequestForm(false);
      setTenantId("");
      setReason("");
      setDurationHours(4);
      queryClient.invalidateQueries({ queryKey: ["platform", "support-access-grants"] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsBusy(false);
    }
  };

  const approveGrant = async (grant: SupportAccessGrantRead) => {
    setError(null);
    setIsBusy(true);
    try {
      await apiClient.post(
        `/api/platform/support-access-grants/${grant.id}/approve`,
        undefined,
        { tenant_id: grant.tenant_id },
      );
      queryClient.invalidateQueries({ queryKey: ["platform", "support-access-grants"] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsBusy(false);
    }
  };

  const revokeGrant = async (grant: SupportAccessGrantRead) => {
    setError(null);
    setIsBusy(true);
    try {
      await apiClient.post(
        `/api/platform/support-access-grants/${grant.id}/revoke`,
        undefined,
        { tenant_id: grant.tenant_id },
      );
      queryClient.invalidateQueries({ queryKey: ["platform", "support-access-grants"] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-ink-900">Support Access</h1>
          <p className="text-sm text-ink-500">
            Temporary access to a tenant&apos;s workspace for support purposes. Every request needs
            approval from a different platform admin before it becomes active.
          </p>
        </div>
        <Button size="sm" onClick={() => setShowRequestForm((v) => !v)}>
          {showRequestForm ? "Cancel" : "Request access"}
        </Button>
      </div>

      {error ? <Alert tone="error">{error}</Alert> : null}

      {showRequestForm ? (
        <Card>
          <CardHeader title="New request" />
          <div className="flex flex-col gap-3">
            <label className="text-xs font-medium text-ink-700" htmlFor="grant-tenant">
              Tenant
            </label>
            <select
              id="grant-tenant"
              value={tenantId}
              onChange={(e) => setTenantId(e.target.value)}
              className="h-9 w-full max-w-sm rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
            >
              <option value="">Select a tenant…</option>
              {tenants.map((tenant) => (
                <option key={tenant.id} value={tenant.id}>
                  {tenant.name}
                </option>
              ))}
            </select>

            <label className="text-xs font-medium text-ink-700" htmlFor="grant-reason">
              Reason
            </label>
            <textarea
              id="grant-reason"
              rows={2}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Required — this is written to the audit trail and visible to the tenant."
              className="max-w-lg rounded border border-surface-border bg-surface-800 px-3 py-2 text-sm text-ink-900"
            />

            <label className="text-xs font-medium text-ink-700" htmlFor="grant-duration">
              Duration once approved (hours)
            </label>
            <input
              id="grant-duration"
              type="number"
              min={1}
              max={24}
              value={durationHours}
              onChange={(e) => setDurationHours(Number(e.target.value))}
              className="h-9 w-24 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
            />

            <Button
              className="w-fit"
              isLoading={isBusy}
              disabled={!tenantId || reason.trim().length < 10}
              onClick={submitRequest}
            >
              Submit request
            </Button>
          </div>
        </Card>
      ) : null}

      <Card>
        <CardHeader title="Filter" />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="h-9 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
        >
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="active">Active</option>
          <option value="revoked">Revoked</option>
        </select>
      </Card>

      <Card>
        <CardHeader title={`Grants (${grants.length})`} />
        {grants.length > 0 ? (
          <div className="flex flex-col gap-3">
            {grants.map((grant) => {
              const isOwnRequest = grant.requested_by_user_id === me?.user.id;
              return (
                <div key={grant.id} className="rounded border border-surface-border p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-medium text-ink-900">{tenantName(grant.tenant_id)}</span>
                      <StatusBadge label={grant.status} tone={statusTone(grant.status)} />
                    </div>
                    <div className="flex gap-2">
                      {grant.status === "active" && grant.platform_user_id === me?.user.id ? (
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => router.push(`/platform/tenants/${grant.tenant_id}/workspace`)}
                        >
                          View workspace
                        </Button>
                      ) : null}
                      {grant.status === "pending" ? (
                        <Button
                          size="sm"
                          isLoading={isBusy}
                          disabled={isOwnRequest}
                          title={isOwnRequest ? "You cannot approve your own request." : undefined}
                          onClick={() => approveGrant(grant)}
                        >
                          Approve
                        </Button>
                      ) : null}
                      {grant.status !== "revoked" ? (
                        <Button
                          size="sm"
                          variant="secondary"
                          isLoading={isBusy}
                          onClick={() => revokeGrant(grant)}
                        >
                          {grant.status === "pending" ? "Reject" : "Revoke"}
                        </Button>
                      ) : null}
                    </div>
                  </div>
                  <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-ink-500 sm:grid-cols-4">
                    <div>
                      <dt className="font-medium text-ink-700">Requested by</dt>
                      <dd>{grant.requested_by_email ?? grant.requested_by_user_id}</dd>
                    </div>
                    <div>
                      <dt className="font-medium text-ink-700">Approved by</dt>
                      <dd>{grant.approved_by_email ?? "—"}</dd>
                    </div>
                    <div>
                      <dt className="font-medium text-ink-700">Expires</dt>
                      <dd>{grant.expires_at ? new Date(grant.expires_at).toLocaleString() : "—"}</dd>
                    </div>
                    <div>
                      <dt className="font-medium text-ink-700">Requested duration</dt>
                      <dd>{grant.requested_duration_hours ?? "—"}h</dd>
                    </div>
                  </dl>
                  <p className="mt-2 text-xs text-ink-500">{grant.reason}</p>
                  {isOwnRequest && grant.status === "pending" ? (
                    <p className="mt-1 text-xs text-ink-500">
                      Waiting on a different platform admin to approve this request.
                    </p>
                  ) : null}
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-ink-500">No matching support access grants.</p>
        )}
      </Card>
    </div>
  );
}
