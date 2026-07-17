"use client";

import { Banner, Card } from "@gridkeep/ui";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AuditLogEntry } from "@/lib/types";

export default function AuditPage() {
  const auditQuery = useQuery<AuditLogEntry[]>({
    queryKey: ["audit-logs"],
    queryFn: () => api.get<AuditLogEntry[]>("/audit/logs"),
  });

  if (auditQuery.isError) {
    return <Banner tone="info">You don&apos;t have permission to view the audit log.</Banner>;
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">Audit Log</h1>
      <Card>
        {auditQuery.data && auditQuery.data.length > 0 ? (
          <ul className="divide-y divide-slate-100 dark:divide-slate-800">
            {auditQuery.data.map((entry) => (
              <li key={entry.id} className="py-3 text-sm">
                <p className="font-medium">{entry.action}</p>
                <p className="text-slate-500 dark:text-slate-400">
                  {new Date(entry.created_at).toLocaleString()}
                  {entry.resource_type && ` · ${entry.resource_type}`}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-500 dark:text-slate-400">No audit events yet.</p>
        )}
      </Card>
    </div>
  );
}
