"use client";

import { Alert, Badge, Button, Card } from "@leadflow/ui";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { apiFetch } from "@/lib/api-client";
import { useCurrentTenant } from "@/hooks/useCurrentTenant";
import { PRIORITY_LABELS, PRIORITY_TONES, type DashboardReportOut } from "@/lib/types";

interface TenantOut {
  id: string;
  slug: string;
  name: string;
  status: string;
  timezone: string;
  currency: string;
}

interface TenantSettingsOut {
  onboarding_completed_at: string | null;
}

interface MemberOut {
  id: string;
  status: string;
}

interface InvitationOut {
  id: string;
  status: string;
}

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <Card>
      <p className="text-xs uppercase tracking-wide text-surface-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-surface-50">{value}</p>
    </Card>
  );
}

export default function DashboardPage() {
  const { tenantId, membership } = useCurrentTenant();
  const canManageUsers = membership?.role.permissions.some((p) => p.code === "users.manage") ?? false;
  const canViewReports = membership?.role.permissions.some((p) => p.code === "reports.view") ?? false;

  const tenantQuery = useQuery({
    queryKey: ["tenant", tenantId],
    queryFn: () => apiFetch<TenantOut>("/tenants/me"),
    enabled: Boolean(tenantId),
  });

  const settingsQuery = useQuery({
    queryKey: ["tenant-settings", tenantId],
    queryFn: () => apiFetch<TenantSettingsOut>("/tenants/me/settings"),
    enabled: Boolean(tenantId),
  });

  const membersQuery = useQuery({
    queryKey: ["members", tenantId],
    queryFn: () => apiFetch<MemberOut[]>("/tenants/me/members"),
    enabled: Boolean(tenantId) && canManageUsers,
  });

  const invitationsQuery = useQuery({
    queryKey: ["invitations", tenantId],
    queryFn: () => apiFetch<InvitationOut[]>("/tenants/me/invitations"),
    enabled: Boolean(tenantId) && canManageUsers,
  });

  const reportQuery = useQuery({
    queryKey: ["dashboard-report", tenantId],
    queryFn: () => apiFetch<DashboardReportOut>("/tenants/me/reports/dashboard"),
    enabled: Boolean(tenantId) && canViewReports,
  });

  const activeMembers = membersQuery.data?.filter((m) => m.status === "active").length;
  const pendingInvitations = invitationsQuery.data?.filter((i) => i.status === "pending").length;
  const report = reportQuery.data;
  const maxFunnelCount = Math.max(1, ...(report?.pipeline_funnel.map((s) => s.lead_count) ?? [0]));

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold text-surface-50">Dashboard</h1>
      <p className="mb-6 text-sm text-surface-400">
        {tenantQuery.data?.name ?? "…"} · {tenantQuery.data?.timezone} · {tenantQuery.data?.currency}
      </p>

      {settingsQuery.data && !settingsQuery.data.onboarding_completed_at ? (
        <Alert tone="info" className="mb-6 flex items-center justify-between gap-4">
          <span>Finish setting up your workspace to get the most out of LeadFlow.</span>
          <Link href="/onboarding">
            <Button variant="secondary">Continue setup</Button>
          </Link>
        </Alert>
      ) : null}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card>
          <p className="text-xs uppercase tracking-wide text-surface-500">Workspace status</p>
          <div className="mt-2 flex items-center gap-2">
            <span className="text-2xl font-semibold text-surface-50">
              {tenantQuery.data?.status ?? "…"}
            </span>
            {tenantQuery.data?.status === "active" ? (
              <Badge tone="success">active</Badge>
            ) : (
              <Badge tone="warning">{tenantQuery.data?.status}</Badge>
            )}
          </div>
        </Card>

        {canManageUsers ? (
          <>
            <StatCard label="Active team members" value={membersQuery.isLoading ? "…" : (activeMembers ?? 0)} />
            <StatCard
              label="Pending invitations"
              value={invitationsQuery.isLoading ? "…" : (pendingInvitations ?? 0)}
            />
          </>
        ) : null}
      </div>

      {!canViewReports ? (
        <Card className="mt-6">
          <p className="text-sm text-surface-400">
            You don&apos;t have permission to view reports. Ask an Owner, Administrator, or Manager
            for access.
          </p>
        </Card>
      ) : report ? (
        <>
          <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <StatCard label="Total leads" value={report.overview.total_leads} />
            <StatCard label="Hot leads" value={report.overview.hot_leads} />
            <StatCard label="Open tasks" value={report.overview.open_tasks} />
            <StatCard label="Overdue tasks" value={report.overview.overdue_tasks} />
            <StatCard label="Upcoming appointments (7d)" value={report.overview.upcoming_appointments} />
          </div>

          <Card className="mt-6">
            <h2 className="mb-4 text-sm font-semibold text-surface-100">Pipeline funnel</h2>
            <div className="space-y-2">
              {report.pipeline_funnel.map((stage) => (
                <div key={stage.stage_id} className="flex items-center gap-3">
                  <span className="w-40 truncate text-sm text-surface-300">{stage.name}</span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-800">
                    <div
                      className={
                        "h-full rounded-full " +
                        (stage.is_won
                          ? "bg-emerald-500"
                          : stage.is_lost
                            ? "bg-red-500"
                            : "bg-accent-500")
                      }
                      style={{ width: `${(stage.lead_count / maxFunnelCount) * 100}%` }}
                    />
                  </div>
                  <span className="w-8 text-right text-sm text-surface-400">{stage.lead_count}</span>
                </div>
              ))}
            </div>
          </Card>

          <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card>
              <h2 className="mb-4 text-sm font-semibold text-surface-100">Lead sources</h2>
              <div className="space-y-2">
                {report.lead_sources.map((s) => (
                  <div key={s.source} className="flex items-center justify-between text-sm">
                    <span className="text-surface-300">{s.source}</span>
                    <span className="text-surface-400">{s.count}</span>
                  </div>
                ))}
                {report.lead_sources.length === 0 ? (
                  <p className="text-sm text-surface-500">No leads yet.</p>
                ) : null}
              </div>
            </Card>

            <Card>
              <h2 className="mb-4 text-sm font-semibold text-surface-100">Score distribution</h2>
              <div className="flex flex-wrap gap-2">
                {report.score_distribution.map((p) => (
                  <Badge key={p.priority} tone={PRIORITY_TONES[p.priority] ?? "neutral"}>
                    {PRIORITY_LABELS[p.priority] ?? p.priority}: {p.count}
                  </Badge>
                ))}
                {report.score_distribution.length === 0 ? (
                  <p className="text-sm text-surface-500">No leads yet.</p>
                ) : null}
              </div>
            </Card>
          </div>

          <Card className="mt-6">
            <h2 className="mb-4 text-sm font-semibold text-surface-100">Team performance</h2>
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-surface-800 text-surface-500">
                  <th className="pb-2 font-medium">Member</th>
                  <th className="pb-2 font-medium">Leads assigned</th>
                  <th className="pb-2 font-medium">Leads won</th>
                </tr>
              </thead>
              <tbody>
                {report.team_performance.map((m) => (
                  <tr key={m.membership_id} className="border-b border-surface-900">
                    <td className="py-2 text-surface-200">{m.member_name}</td>
                    <td className="py-2 text-surface-400">{m.leads_assigned}</td>
                    <td className="py-2 text-surface-400">{m.leads_won}</td>
                  </tr>
                ))}
                {report.team_performance.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="py-4 text-center text-surface-500">
                      No active team members yet.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </Card>

          <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card>
              <h2 className="mb-4 text-sm font-semibold text-surface-100">Tasks (last 30 days)</h2>
              <div className="flex gap-4 text-sm">
                <span className="text-surface-300">Open: {report.task_stats.open}</span>
                <span className="text-surface-300">Overdue: {report.task_stats.overdue}</span>
                <span className="text-surface-300">
                  Completed: {report.task_stats.completed_last_30_days}
                </span>
              </div>
            </Card>
            <Card>
              <h2 className="mb-4 text-sm font-semibold text-surface-100">Appointments</h2>
              <div className="flex flex-wrap gap-3 text-sm">
                <span className="text-surface-300">Scheduled: {report.appointment_stats.scheduled}</span>
                <span className="text-surface-300">Confirmed: {report.appointment_stats.confirmed}</span>
                <span className="text-surface-300">Completed: {report.appointment_stats.completed}</span>
                <span className="text-surface-300">Cancelled: {report.appointment_stats.cancelled}</span>
                <span className="text-surface-300">No-show: {report.appointment_stats.no_show}</span>
              </div>
            </Card>
          </div>
        </>
      ) : (
        <Card className="mt-6">
          <p className="text-sm text-surface-400">Loading reports…</p>
        </Card>
      )}
    </div>
  );
}
