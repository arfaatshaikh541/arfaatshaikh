"use client";

import { use, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api-client";
import type { TenantSummary } from "@/lib/types";

interface Plan {
  id: string;
  code: string;
  name: string;
}

interface TenantEntitlements {
  plan_code: string | null;
  subscription_status: string | null;
  modules: Record<string, boolean>;
  features: Record<string, { enabled?: boolean; limit?: number | null }>;
}

interface UsageItem {
  metric_code: string;
  value: number;
}

const STATUSES = ["active", "read_only", "suspended", "archived"] as const;

export default function TenantDetailPage({ params }: { params: Promise<{ tenantId: string }> }) {
  const { tenantId } = use(params);
  const queryClient = useQueryClient();

  const tenantQuery = useQuery({
    queryKey: ["platform", "tenant", tenantId],
    queryFn: () => api.get<TenantSummary>(`/platform/tenants/${tenantId}`),
  });
  const entitlementsQuery = useQuery({
    queryKey: ["platform", "tenant", tenantId, "entitlements"],
    queryFn: () => api.get<TenantEntitlements>(`/platform/tenants/${tenantId}/entitlements`),
  });
  const usageQuery = useQuery({
    queryKey: ["platform", "tenant", tenantId, "usage"],
    queryFn: () => api.get<UsageItem[]>(`/platform/tenants/${tenantId}/usage`),
  });
  const plansQuery = useQuery({ queryKey: ["platform", "plans"], queryFn: () => api.get<Plan[]>("/platform/plans") });

  const invalidateTenant = () => {
    queryClient.invalidateQueries({ queryKey: ["platform", "tenant", tenantId] });
    queryClient.invalidateQueries({ queryKey: ["platform", "tenants"] });
  };

  const statusMutation = useMutation({
    mutationFn: (status: string) => api.post(`/platform/tenants/${tenantId}/status`, { status }),
    onSuccess: invalidateTenant,
  });

  const planMutation = useMutation({
    mutationFn: (plan_code: string) => api.post(`/platform/tenants/${tenantId}/plan`, { plan_code }),
    onSuccess: invalidateTenant,
  });

  const [overrideFeature, setOverrideFeature] = useState("");
  const [overrideEnabled, setOverrideEnabled] = useState(true);
  const overrideMutation = useMutation({
    mutationFn: () =>
      api.post(`/platform/tenants/${tenantId}/overrides`, {
        feature_code: overrideFeature,
        config: { enabled: overrideEnabled },
        reason: "Granted via platform admin console",
      }),
    onSuccess: () => {
      setOverrideFeature("");
      invalidateTenant();
    },
  });

  if (tenantQuery.isLoading) return <p className="text-sm text-ink-muted">Loading…</p>;
  const tenant = tenantQuery.data;
  if (!tenant) return <Alert tone="error">Tenant not found.</Alert>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">{tenant.name}</h1>
        <p className="mt-1 text-sm text-ink-muted">/{tenant.slug}</p>
      </div>

      <Card>
        <CardHeader title="Status" />
        <div className="flex flex-wrap gap-2">
          {STATUSES.map((status) => (
            <Button
              key={status}
              variant={tenant.status === status ? "primary" : "secondary"}
              onClick={() => statusMutation.mutate(status)}
              disabled={statusMutation.isPending}
            >
              {status.replace("_", " ")}
            </Button>
          ))}
        </div>
        {statusMutation.isError && (
          <div className="mt-3">
            <Alert tone="error">
              {statusMutation.error instanceof ApiError ? statusMutation.error.message : "Unable to update status."}
            </Alert>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader title="Plan" description={`Current plan: ${entitlementsQuery.data?.plan_code ?? "—"}`} />
        <div className="flex flex-wrap gap-2">
          {plansQuery.data?.map((plan) => (
            <Button
              key={plan.id}
              variant={entitlementsQuery.data?.plan_code === plan.code ? "primary" : "secondary"}
              onClick={() => planMutation.mutate(plan.code)}
              disabled={planMutation.isPending}
            >
              {plan.name}
            </Button>
          ))}
        </div>
      </Card>

      <Card>
        <CardHeader title="Modules" />
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {entitlementsQuery.data &&
            Object.entries(entitlementsQuery.data.modules).map(([code, enabled]) => (
              <div
                key={code}
                className={`rounded-md border px-3 py-2 text-sm capitalize ${
                  enabled ? "border-accent/40 bg-accent/10 text-ink" : "border-surface-border text-ink-faint"
                }`}
              >
                {code.replaceAll("_", " ")}
              </div>
            ))}
        </div>
      </Card>

      <Card>
        <CardHeader title="Grant a feature override" description="Overrides always win over the plan's own configuration." />
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <Label htmlFor="feature_code">Feature code</Label>
            <Input id="feature_code" value={overrideFeature} onChange={(e) => setOverrideFeature(e.target.value)} placeholder="whatsapp" />
          </div>
          <label className="mb-0.5 flex items-center gap-2 text-sm text-ink-muted">
            <input type="checkbox" checked={overrideEnabled} onChange={(e) => setOverrideEnabled(e.target.checked)} />
            Enabled
          </label>
          <Button onClick={() => overrideMutation.mutate()} disabled={!overrideFeature || overrideMutation.isPending}>
            {overrideMutation.isPending ? "Granting…" : "Grant override"}
          </Button>
        </div>
        {overrideMutation.isSuccess && (
          <div className="mt-3">
            <Alert tone="success">Override granted.</Alert>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader title="Usage" />
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {usageQuery.data?.map((item) => (
            <div key={item.metric_code} className="rounded-md border border-surface-border px-3 py-2 text-sm">
              <p className="text-ink-faint">{item.metric_code}</p>
              <p className="text-ink">{item.value}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
