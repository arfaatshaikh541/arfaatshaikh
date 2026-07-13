"use client";

import { Alert, Badge, Button, Card, Input, Label } from "@leadflow/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";

import { ApiError, apiFetch } from "@/lib/api-client";
import type { PlatformTenantOut, SubscriptionOut, SubscriptionPlanOut } from "@/lib/types";
import { SUBSCRIPTION_STATUSES } from "@/lib/types";

const STATUS_TONE: Record<string, "success" | "warning" | "danger"> = {
  active: "success",
  suspended: "warning",
  archived: "danger",
};

export default function PlatformTenantDetailPage() {
  const params = useParams<{ id: string }>();
  const tenantId = params.id;
  const queryClient = useQueryClient();
  const [serverError, setServerError] = useState<string | null>(null);
  const [newStatus, setNewStatus] = useState("active");
  const [statusReason, setStatusReason] = useState("");
  const [selectedPlanId, setSelectedPlanId] = useState("");
  const [subscriptionStatus, setSubscriptionStatus] = useState("active");

  const tenantQuery = useQuery({
    queryKey: ["platform-tenant", tenantId],
    queryFn: () => apiFetch<PlatformTenantOut>(`/platform/tenants/${tenantId}`, { withTenant: false }),
    enabled: Boolean(tenantId),
  });
  const subscriptionQuery = useQuery({
    queryKey: ["platform-tenant-subscription", tenantId],
    queryFn: () =>
      apiFetch<SubscriptionOut | null>(`/platform/tenants/${tenantId}/subscription`, {
        withTenant: false,
      }),
    enabled: Boolean(tenantId),
  });
  const plansQuery = useQuery({
    queryKey: ["platform-plans"],
    queryFn: () => apiFetch<SubscriptionPlanOut[]>("/platform/plans", { withTenant: false }),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["platform-tenant", tenantId] });
    queryClient.invalidateQueries({ queryKey: ["platform-tenant-subscription", tenantId] });
    queryClient.invalidateQueries({ queryKey: ["platform-tenants"] });
  };

  const statusMutation = useMutation({
    mutationFn: () =>
      apiFetch<PlatformTenantOut>(`/platform/tenants/${tenantId}/status`, {
        method: "POST",
        withTenant: false,
        body: { status: newStatus, reason: statusReason },
      }),
    onSuccess: () => {
      setStatusReason("");
      invalidate();
    },
    onError: (err) => setServerError(err instanceof ApiError ? err.message : "Something went wrong."),
  });

  const subscriptionMutation = useMutation({
    mutationFn: () =>
      apiFetch<SubscriptionOut>(`/platform/tenants/${tenantId}/subscription`, {
        method: "POST",
        withTenant: false,
        body: { plan_id: selectedPlanId, status: subscriptionStatus },
      }),
    onSuccess: invalidate,
    onError: (err) => setServerError(err instanceof ApiError ? err.message : "Something went wrong."),
  });

  const tenant = tenantQuery.data;
  const plansById = new Map((plansQuery.data ?? []).map((p) => [p.id, p]));
  const currentPlan = subscriptionQuery.data ? plansById.get(subscriptionQuery.data.plan_id) : null;

  if (!tenant) {
    return <p className="text-sm text-surface-400">Loading…</p>;
  }

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="mb-1 text-xl font-semibold text-surface-50">{tenant.name}</h1>
        <p className="text-sm text-surface-500">
          {tenant.slug} · {tenant.timezone} · {tenant.currency}
        </p>
      </div>

      {serverError ? (
        <Alert tone="error">{serverError}</Alert>
      ) : null}

      <Card>
        <h2 className="mb-3 text-sm font-semibold text-surface-100">Status</h2>
        <div className="mb-3 flex items-center gap-2">
          <span className="text-sm text-surface-400">Current:</span>
          <Badge tone={STATUS_TONE[tenant.status] ?? "neutral"}>{tenant.status}</Badge>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <Label htmlFor="new-status">New status</Label>
            <select
              id="new-status"
              className="rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50"
              value={newStatus}
              onChange={(e) => setNewStatus(e.target.value)}
            >
              <option value="active">active</option>
              <option value="suspended">suspended</option>
              <option value="archived">archived</option>
            </select>
          </div>
          <div className="flex-1">
            <Label htmlFor="status-reason">Reason</Label>
            <Input
              id="status-reason"
              value={statusReason}
              onChange={(e) => setStatusReason(e.target.value)}
              placeholder="Why is this status changing?"
            />
          </div>
          <Button
            disabled={statusReason.trim().length < 3}
            loading={statusMutation.isPending}
            onClick={() => {
              setServerError(null);
              statusMutation.mutate();
            }}
          >
            Update status
          </Button>
        </div>
      </Card>

      <Card>
        <h2 className="mb-3 text-sm font-semibold text-surface-100">Subscription</h2>
        {subscriptionQuery.data ? (
          <p className="mb-3 text-sm text-surface-400">
            Current plan: <span className="text-surface-200">{currentPlan?.name ?? "Unknown"}</span> ·
            Status: <Badge tone="neutral">{subscriptionQuery.data.status}</Badge>
          </p>
        ) : (
          <p className="mb-3 text-sm text-surface-500">No subscription assigned yet.</p>
        )}
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <Label htmlFor="assign-plan">Plan</Label>
            <select
              id="assign-plan"
              className="w-56 rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50"
              value={selectedPlanId}
              onChange={(e) => setSelectedPlanId(e.target.value)}
            >
              <option value="">Select a plan…</option>
              {plansQuery.data?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.code})
                </option>
              ))}
            </select>
          </div>
          <div>
            <Label htmlFor="assign-status">Status</Label>
            <select
              id="assign-status"
              className="rounded-md border border-surface-700 bg-surface-900 px-3 py-2 text-sm text-surface-50"
              value={subscriptionStatus}
              onChange={(e) => setSubscriptionStatus(e.target.value)}
            >
              {SUBSCRIPTION_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <Button
            disabled={!selectedPlanId}
            loading={subscriptionMutation.isPending}
            onClick={() => {
              setServerError(null);
              subscriptionMutation.mutate();
            }}
          >
            Assign subscription
          </Button>
        </div>
      </Card>
    </div>
  );
}
