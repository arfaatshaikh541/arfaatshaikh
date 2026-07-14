"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Card, CardHeader } from "@/components/ui/card";
import { api } from "@/lib/api-client";
import type { TenantSummary } from "@/lib/types";

export default function PlatformOverviewPage() {
  const { data } = useQuery({ queryKey: ["platform", "tenants"], queryFn: () => api.get<TenantSummary[]>("/platform/tenants") });

  const counts = {
    total: data?.length ?? 0,
    active: data?.filter((t) => t.status === "active").length ?? 0,
    suspended: data?.filter((t) => t.status === "suspended").length ?? 0,
    readOnly: data?.filter((t) => t.status === "read_only").length ?? 0,
    archived: data?.filter((t) => t.status === "archived").length ?? 0,
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Platform overview</h1>
        <p className="mt-1 text-sm text-ink-muted">All tenants across the platform.</p>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Card>
          <p className="text-xs text-ink-faint">Total tenants</p>
          <p className="mt-1 text-2xl font-semibold text-ink">{counts.total}</p>
        </Card>
        <Card>
          <p className="text-xs text-ink-faint">Active</p>
          <p className="mt-1 text-2xl font-semibold text-emerald-400">{counts.active}</p>
        </Card>
        <Card>
          <p className="text-xs text-ink-faint">Suspended / read-only</p>
          <p className="mt-1 text-2xl font-semibold text-amber-400">{counts.suspended + counts.readOnly}</p>
        </Card>
        <Card>
          <p className="text-xs text-ink-faint">Archived</p>
          <p className="mt-1 text-2xl font-semibold text-ink-faint">{counts.archived}</p>
        </Card>
      </div>

      <Card>
        <CardHeader title="Quick links" />
        <div className="flex gap-3">
          <Link href="/admin/tenants" className="text-sm text-accent hover:text-accent-hover">
            Manage tenants →
          </Link>
          <Link href="/admin/plans" className="text-sm text-accent hover:text-accent-hover">
            Manage plans →
          </Link>
          <Link href="/admin/audit-logs" className="text-sm text-accent hover:text-accent-hover">
            View audit logs →
          </Link>
        </div>
      </Card>
    </div>
  );
}
