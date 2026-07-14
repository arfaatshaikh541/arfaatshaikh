"use client";

import { Card, CardHeader } from "@/components/ui/card";
import { useAuth } from "@/lib/auth-context";
import { useEntitlements } from "@/lib/entitlements";

export default function DashboardPage() {
  const { user } = useAuth();
  const { data: entitlements, isLoading } = useEntitlements();

  const enabledModules = entitlements ? Object.entries(entitlements.modules).filter(([, enabled]) => enabled) : [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">
          Welcome back, {user?.first_name}
        </h1>
        <p className="mt-1 text-sm text-ink-muted">
          {entitlements ? `${entitlements.role_name} · Plan: ${entitlements.plan_code ?? "—"}` : "Loading…"}
        </p>
      </div>

      <Card>
        <CardHeader
          title="Enabled modules"
          description="Modules included in this workspace's current subscription."
        />
        {isLoading && <p className="text-sm text-ink-muted">Loading…</p>}
        {!isLoading && enabledModules.length === 0 && (
          <p className="text-sm text-ink-muted">No modules are enabled for this workspace yet.</p>
        )}
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {enabledModules.map(([code]) => (
            <div
              key={code}
              className="rounded-md border border-surface-border bg-surface px-3 py-2 text-sm capitalize text-ink"
            >
              {code.replaceAll("_", " ")}
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <CardHeader title="What's next" />
        <p className="text-sm text-ink-muted">
          Lead capture, CRM pipeline, and the rest of this workspace&apos;s day-to-day tools are built out module by
          module in upcoming milestones. This dashboard will surface live lead and pipeline metrics once the CRM
          module (Milestone 2) ships.
        </p>
      </Card>
    </div>
  );
}
