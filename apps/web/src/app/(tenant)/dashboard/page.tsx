"use client";

import { Badge, Card } from "@leadflow/ui";
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import { useCurrentTenant } from "@/hooks/useCurrentTenant";

interface TenantOut {
  id: string;
  slug: string;
  name: string;
  status: string;
  timezone: string;
  currency: string;
}

interface MemberOut {
  id: string;
  status: string;
}

interface InvitationOut {
  id: string;
  status: string;
}

export default function DashboardPage() {
  const { tenantId, membership } = useCurrentTenant();
  const canManageUsers = membership?.role.permissions.some((p) => p.code === "users.manage") ?? false;

  const tenantQuery = useQuery({
    queryKey: ["tenant", tenantId],
    queryFn: () => apiFetch<TenantOut>("/tenants/me"),
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

  const activeMembers = membersQuery.data?.filter((m) => m.status === "active").length;
  const pendingInvitations = invitationsQuery.data?.filter((i) => i.status === "pending").length;

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold text-surface-50">Dashboard</h1>
      <p className="mb-6 text-sm text-surface-400">
        {tenantQuery.data?.name ?? "…"} · {tenantQuery.data?.timezone} · {tenantQuery.data?.currency}
      </p>

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
            <Card>
              <p className="text-xs uppercase tracking-wide text-surface-500">Active team members</p>
              <p className="mt-2 text-2xl font-semibold text-surface-50">
                {membersQuery.isLoading ? "…" : (activeMembers ?? 0)}
              </p>
            </Card>
            <Card>
              <p className="text-xs uppercase tracking-wide text-surface-500">Pending invitations</p>
              <p className="mt-2 text-2xl font-semibold text-surface-50">
                {invitationsQuery.isLoading ? "…" : (pendingInvitations ?? 0)}
              </p>
            </Card>
          </>
        ) : null}
      </div>

      <Card className="mt-6">
        <p className="text-sm text-surface-300">
          Leads, the CRM pipeline, scoring, booking and reporting are built in later milestones on
          top of this foundation (multi-tenancy, auth, RBAC, tenant settings). See{" "}
          <code className="rounded bg-surface-800 px-1 py-0.5 text-xs">
            docs/product/milestone-1-acceptance-criteria.md
          </code>{" "}
          for what Milestone 1 covers.
        </p>
      </Card>
    </div>
  );
}
