"use client";

import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api-client";

interface AuditLogEntry {
  id: string;
  tenant_id: string | null;
  actor_user_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  created_at: string;
}

export default function AuditLogsPage() {
  const { data } = useQuery({
    queryKey: ["platform", "audit-logs"],
    queryFn: () => api.get<AuditLogEntry[]>("/platform/audit-logs?page=1&page_size=100"),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Audit logs</h1>
        <p className="mt-1 text-sm text-ink-muted">Platform-wide immutable event history.</p>
      </div>
      <Card>
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-surface-border text-ink-faint">
              <th className="pb-2 font-medium">Action</th>
              <th className="pb-2 font-medium">Entity</th>
              <th className="pb-2 font-medium">Tenant</th>
              <th className="pb-2 font-medium">When</th>
            </tr>
          </thead>
          <tbody>
            {data?.map((entry) => (
              <tr key={entry.id} className="border-b border-surface-border/60">
                <td className="py-2 text-ink">{entry.action}</td>
                <td className="py-2 text-ink-muted">{entry.entity_type}</td>
                <td className="py-2 text-ink-muted">{entry.tenant_id ? entry.tenant_id.slice(0, 8) : "—"}</td>
                <td className="py-2 text-ink-muted">{new Date(entry.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
