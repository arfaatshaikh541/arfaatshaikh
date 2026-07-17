"use client";

import { Alert, Card, CardHeader, SeverityBadge, StatusBadge } from "@gridkeep/ui";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";

import { apiClient, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { FindingListItem, IncidentListItem, TenantWorkspaceSnapshotRead } from "@/lib/types";

const INCIDENT_STATUS_TONE: Record<string, "positive" | "warning" | "neutral"> = {
  declared: "warning",
  investigating: "warning",
  contained: "neutral",
  resolved: "positive",
  closed: "positive",
};

export default function TenantWorkspaceSnapshotPage() {
  const params = useParams<{ tenantId: string }>();
  const tenantId = params.tenantId;
  const { hasPlatformPermission } = useAuth();
  const canRequest = hasPlatformPermission("platform.support_access");

  const snapshotQuery = useQuery({
    queryKey: ["platform", "tenants", tenantId, "workspace-snapshot"],
    queryFn: () =>
      apiClient.get<TenantWorkspaceSnapshotRead>(`/api/platform/tenants/${tenantId}/workspace-snapshot`),
    enabled: canRequest,
    retry: false,
  });

  const findingsQuery = useQuery({
    queryKey: ["platform", "tenants", tenantId, "findings"],
    queryFn: () => apiClient.get<FindingListItem[]>(`/api/platform/tenants/${tenantId}/findings`),
    enabled: canRequest && !snapshotQuery.isError,
    retry: false,
  });

  const incidentsQuery = useQuery({
    queryKey: ["platform", "tenants", tenantId, "incidents"],
    queryFn: () => apiClient.get<IncidentListItem[]>(`/api/platform/tenants/${tenantId}/incidents`),
    enabled: canRequest && !snapshotQuery.isError,
    retry: false,
  });

  if (!canRequest) {
    return <p className="text-sm text-ink-500">Not visible to your platform role.</p>;
  }

  if (snapshotQuery.isError) {
    const err = snapshotQuery.error;
    const grantRequired =
      err instanceof ApiError && err.details?.support_access_grant_required === true;
    return (
      <div className="flex flex-col gap-4">
        <Alert tone="error">
          {grantRequired
            ? "You need an active support access grant for this tenant to view its workspace."
            : err instanceof ApiError
              ? err.message
              : "Something went wrong."}
        </Alert>
        <Link href="/platform/support-access" className="text-sm text-accent underline">
          Go to Support Access to request one
        </Link>
      </div>
    );
  }

  const snapshot = snapshotQuery.data;
  if (!snapshot) {
    return <p className="text-sm text-ink-500">Loading…</p>;
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-ink-900">{snapshot.tenant_name}</h1>
        <div className="mt-1 flex items-center gap-2">
          <StatusBadge label={snapshot.tenant_status.replace(/_/g, " ")} tone="neutral" />
          <span className="text-sm text-ink-500">Read-only support view</span>
          <span className="text-sm text-ink-500">
            · Your access expires {new Date(snapshot.access_expires_at).toLocaleString()}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader title="Open findings" />
          <p className="text-2xl font-semibold text-ink-900">{snapshot.open_findings_total}</p>
        </Card>
        <Card>
          <CardHeader title="Open incidents" />
          <p className="text-2xl font-semibold text-ink-900">{snapshot.open_incidents_total}</p>
        </Card>
        <Card>
          <CardHeader title="Connected integrations" />
          <p className="text-2xl font-semibold text-ink-900">{snapshot.connected_integrations_count}</p>
        </Card>
      </div>

      <Card>
        <CardHeader title={`Members (${snapshot.members.length})`} />
        {snapshot.members.length > 0 ? (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-surface-border text-ink-500">
                <th className="py-2 pr-4 font-medium">Name</th>
                <th className="py-2 pr-4 font-medium">Email</th>
                <th className="py-2 pr-4 font-medium">Role</th>
                <th className="py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {snapshot.members.map((member) => (
                <tr key={member.user_id} className="border-b border-surface-border/50">
                  <td className="py-2 pr-4 text-ink-900">{member.full_name}</td>
                  <td className="py-2 pr-4 text-ink-700">{member.email}</td>
                  <td className="py-2 pr-4 text-ink-700">{member.role_name.replace(/_/g, " ")}</td>
                  <td className="py-2 text-ink-500">{member.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-sm text-ink-500">No members.</p>
        )}
      </Card>

      <Card>
        <CardHeader
          title={`All findings (${findingsQuery.data?.length ?? 0})`}
          description="Every finding regardless of status — the tile above counts only open ones."
        />
        {findingsQuery.data && findingsQuery.data.length > 0 ? (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-surface-border text-ink-500">
                <th className="py-2 pr-4 font-medium">Title</th>
                <th className="py-2 pr-4 font-medium">Severity</th>
                <th className="py-2 pr-4 font-medium">Status</th>
                <th className="py-2 font-medium">Asset</th>
              </tr>
            </thead>
            <tbody>
              {findingsQuery.data.map((finding) => (
                <tr key={finding.id} className="border-b border-surface-border/50">
                  <td className="py-2 pr-4 text-ink-900">{finding.title}</td>
                  <td className="py-2 pr-4">
                    <SeverityBadge severity={finding.severity as "critical" | "high" | "medium" | "low"} />
                  </td>
                  <td className="py-2 pr-4 text-ink-700">{finding.status.replace(/_/g, " ")}</td>
                  <td className="py-2 text-ink-500">{finding.asset_display_name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-sm text-ink-500">No findings.</p>
        )}
      </Card>

      <Card>
        <CardHeader title={`Incidents (${incidentsQuery.data?.length ?? 0})`} />
        {incidentsQuery.data && incidentsQuery.data.length > 0 ? (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-surface-border text-ink-500">
                <th className="py-2 pr-4 font-medium">Title</th>
                <th className="py-2 pr-4 font-medium">Severity</th>
                <th className="py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {incidentsQuery.data.map((incident) => (
                <tr key={incident.id} className="border-b border-surface-border/50">
                  <td className="py-2 pr-4 text-ink-900">{incident.title}</td>
                  <td className="py-2 pr-4">
                    <SeverityBadge severity={incident.severity as "critical" | "high" | "medium" | "low"} />
                  </td>
                  <td className="py-2">
                    <StatusBadge
                      label={incident.status}
                      tone={INCIDENT_STATUS_TONE[incident.status] ?? "neutral"}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-sm text-ink-500">No incidents.</p>
        )}
      </Card>
    </div>
  );
}
