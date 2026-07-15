"use client";

import { Alert, Card, CardHeader, StatusBadge } from "@gridkeep/ui";
import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { EntitlementsRead, SubscriptionRead } from "@/lib/types";

export default function SubscriptionSettingsPage() {
  const { hasPermission } = useAuth();
  const canView = hasPermission("subscriptions.view");

  const subscriptionQuery = useQuery({
    queryKey: ["subscriptions", "current"],
    queryFn: () => apiClient.get<SubscriptionRead>("/api/subscriptions/current"),
    enabled: canView,
  });

  const entitlementsQuery = useQuery({
    queryKey: ["subscriptions", "entitlements"],
    queryFn: () => apiClient.get<EntitlementsRead>("/api/subscriptions/entitlements"),
    enabled: canView,
  });

  if (!canView) {
    return <Alert tone="info">You don&apos;t have permission to view subscription details.</Alert>;
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-ink-900">Subscription</h1>
        <p className="text-sm text-ink-500">Your current plan and the modules it entitles.</p>
      </div>

      <Card>
        <CardHeader title="Plan" />
        {subscriptionQuery.data ? (
          <div className="flex items-center gap-3">
            <p className="text-sm text-ink-900">{subscriptionQuery.data.plan_name}</p>
            <StatusBadge
              label={subscriptionQuery.data.status}
              tone={subscriptionQuery.data.status === "active" ? "positive" : "warning"}
            />
          </div>
        ) : (
          <p className="text-sm text-ink-500">No active subscription found.</p>
        )}
      </Card>

      <Card>
        <CardHeader title="Entitled modules" description="Features included in your current plan." />
        <ul className="flex flex-wrap gap-1.5">
          {entitlementsQuery.data?.entitled_modules.map((moduleKey) => (
            <li key={moduleKey}>
              <StatusBadge label={moduleKey.replace(/_/g, " ")} />
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
