"use client";

import { Card, CardHeader } from "@gridkeep/ui";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { PlatformAuditLogRead, PlatformTenantSummary } from "@/lib/types";

export default function PlatformAuditLogsPage() {
  const { hasPlatformPermission } = useAuth();
  const canView = hasPlatformPermission("platform.audit.view");
  const canManageTenants = hasPlatformPermission("platform.tenants.manage");

  const [tenantId, setTenantId] = useState<string>("");
  const [action, setAction] = useState<string>("");

  const tenantsQuery = useQuery({
    queryKey: ["platform", "tenants"],
    queryFn: () => apiClient.get<PlatformTenantSummary[]>("/api/platform/tenants"),
    enabled: canView && canManageTenants,
  });

  const logsQuery = useQuery({
    queryKey: ["platform", "audit-logs", tenantId, action],
    queryFn: () =>
      apiClient.get<PlatformAuditLogRead[]>("/api/platform/audit-logs", {
        ...(tenantId ? { tenant_id: tenantId } : {}),
        ...(action ? { action } : {}),
        limit: "100",
      }),
    enabled: canView,
  });

  if (!canView) {
    return <p className="text-sm text-ink-500">Not visible to your platform role.</p>;
  }

  const logs = logsQuery.data ?? [];
  const tenants = tenantsQuery.data ?? [];
  const tenantName = (id: string | null) => tenants.find((t) => t.id === id)?.name ?? id ?? "—";

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-ink-900">Platform Audit Log</h1>
        <p className="text-sm text-ink-500">
          Every recorded action across every tenant on the platform, in one place.
        </p>
      </div>

      <Card>
        <CardHeader title="Filters" />
        <div className="flex flex-wrap gap-3">
          {canManageTenants ? (
            <select
              value={tenantId}
              onChange={(e) => setTenantId(e.target.value)}
              className="h-9 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
            >
              <option value="">All tenants</option>
              {tenants.map((tenant) => (
                <option key={tenant.id} value={tenant.id}>
                  {tenant.name}
                </option>
              ))}
            </select>
          ) : null}
          <input
            type="text"
            placeholder="Filter by action (e.g. platform.tenant_status_changed)"
            value={action}
            onChange={(e) => setAction(e.target.value)}
            className="h-9 w-80 rounded border border-surface-border bg-surface-800 px-3 text-sm text-ink-900"
          />
        </div>
      </Card>

      <Card>
        <CardHeader title={`Events (${logs.length})`} />
        {logs.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-surface-border text-ink-500">
                  <th className="py-2 pr-4 font-medium">When</th>
                  <th className="py-2 pr-4 font-medium">Tenant</th>
                  <th className="py-2 pr-4 font-medium">Actor</th>
                  <th className="py-2 pr-4 font-medium">Action</th>
                  <th className="py-2 font-medium">Context</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id} className="border-b border-surface-border/50 align-top">
                    <td className="py-2 pr-4 whitespace-nowrap text-ink-500">
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                    <td className="py-2 pr-4 text-ink-700">
                      {log.tenant_id ? tenantName(log.tenant_id) : "— (platform-level)"}
                    </td>
                    <td className="py-2 pr-4 text-ink-700">{log.actor_label}</td>
                    <td className="py-2 pr-4 text-ink-900">{log.action}</td>
                    <td className="py-2 text-ink-500">
                      {Object.keys(log.context).length > 0 ? (
                        <code className="text-xs">{JSON.stringify(log.context)}</code>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-ink-500">No matching audit events.</p>
        )}
      </Card>
    </div>
  );
}
