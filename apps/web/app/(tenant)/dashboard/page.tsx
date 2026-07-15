"use client";

import { Card, CardHeader, StatusBadge } from "@gridkeep/ui";
import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { EntitlementsRead, SubscriptionRead, TenantRead } from "@/lib/types";

export default function DashboardPage() {
  const { activeMembership, hasPermission } = useAuth();

  const tenantQuery = useQuery({
    queryKey: ["tenancy", "current"],
    queryFn: () => apiClient.get<TenantRead>("/api/tenancy/current"),
  });

  const entitlementsQuery = useQuery({
    queryKey: ["subscriptions", "entitlements"],
    queryFn: () => apiClient.get<EntitlementsRead>("/api/subscriptions/entitlements"),
    enabled: hasPermission("subscriptions.view"),
  });

  const subscriptionQuery = useQuery({
    queryKey: ["subscriptions", "current"],
    queryFn: () => apiClient.get<SubscriptionRead>("/api/subscriptions/current"),
    enabled: hasPermission("subscriptions.view"),
  });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-ink-900">
          {activeMembership?.tenant_name ?? "Dashboard"}
        </h1>
        <p className="text-sm text-ink-500">
          Executive overview — plain-language security posture lands in Milestone 3 (Findings and Risk
          Engine) once assets and findings exist to summarise.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card>
          <CardHeader title="Workspace status" />
          {tenantQuery.data ? (
            <StatusBadge
              label={tenantQuery.data.status}
              tone={tenantQuery.data.status === "active" ? "positive" : "warning"}
            />
          ) : (
            <p className="text-sm text-ink-500">Loading…</p>
          )}
        </Card>

        <Card>
          <CardHeader title="Subscription" />
          {subscriptionQuery.data ? (
            <p className="text-sm text-ink-700">
              {subscriptionQuery.data.plan_name} <span className="text-ink-500">({subscriptionQuery.data.status})</span>
            </p>
          ) : (
            <p className="text-sm text-ink-500">
              {hasPermission("subscriptions.view") ? "Loading…" : "Not visible to your role."}
            </p>
          )}
        </Card>

        <Card>
          <CardHeader title="Entitled modules" />
          {entitlementsQuery.data ? (
            <ul className="flex flex-wrap gap-1.5">
              {entitlementsQuery.data.entitled_modules.map((moduleKey) => (
                <li key={moduleKey}>
                  <StatusBadge label={moduleKey.replace(/_/g, " ")} />
                </li>
              ))}
              {entitlementsQuery.data.entitled_modules.length === 0 ? (
                <p className="text-sm text-ink-500">No modules entitled yet.</p>
              ) : null}
            </ul>
          ) : (
            <p className="text-sm text-ink-500">
              {hasPermission("subscriptions.view") ? "Loading…" : "Not visible to your role."}
            </p>
          )}
        </Card>
      </div>
    </div>
  );
}
