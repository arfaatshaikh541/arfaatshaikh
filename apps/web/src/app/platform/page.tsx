"use client";

import { Card } from "@leadflow/ui";
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import type { PlatformOverviewOut } from "@/lib/types";

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <Card>
      <p className="text-xs uppercase tracking-wide text-surface-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-surface-50">{value}</p>
    </Card>
  );
}

export default function PlatformOverviewPage() {
  const overviewQuery = useQuery({
    queryKey: ["platform-overview"],
    queryFn: () => apiFetch<PlatformOverviewOut>("/platform/overview", { withTenant: false }),
  });
  const overview = overviewQuery.data;

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold text-surface-50">Platform overview</h1>
      <p className="mb-6 text-sm text-surface-400">
        Live figures aggregated across every tenant on the platform.
      </p>

      {overview ? (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <StatCard label="Total tenants" value={overview.total_tenants} />
            <StatCard label="Total leads" value={overview.total_leads} />
            <StatCard label="Total appointments" value={overview.total_appointments} />
          </div>

          <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
            <Card>
              <h2 className="mb-3 text-sm font-semibold text-surface-100">Tenants by status</h2>
              <div className="space-y-2 text-sm">
                {overview.tenants_by_status.map((s) => (
                  <div key={s.status} className="flex items-center justify-between">
                    <span className="text-surface-300">{s.status}</span>
                    <span className="text-surface-400">{s.count}</span>
                  </div>
                ))}
              </div>
            </Card>
            <Card>
              <h2 className="mb-3 text-sm font-semibold text-surface-100">Subscriptions by status</h2>
              <div className="space-y-2 text-sm">
                {overview.subscriptions_by_status.map((s) => (
                  <div key={s.status} className="flex items-center justify-between">
                    <span className="text-surface-300">{s.status}</span>
                    <span className="text-surface-400">{s.count}</span>
                  </div>
                ))}
                {overview.subscriptions_by_status.length === 0 ? (
                  <p className="text-surface-500">No subscriptions yet.</p>
                ) : null}
              </div>
            </Card>
            <Card>
              <h2 className="mb-3 text-sm font-semibold text-surface-100">Subscriptions by plan</h2>
              <div className="space-y-2 text-sm">
                {overview.subscriptions_by_plan.map((p) => (
                  <div key={p.plan_code} className="flex items-center justify-between">
                    <span className="text-surface-300">{p.plan_code}</span>
                    <span className="text-surface-400">{p.count}</span>
                  </div>
                ))}
                {overview.subscriptions_by_plan.length === 0 ? (
                  <p className="text-surface-500">No plans yet.</p>
                ) : null}
              </div>
            </Card>
          </div>
        </>
      ) : (
        <Card>
          <p className="text-sm text-surface-400">Loading…</p>
        </Card>
      )}
    </div>
  );
}
