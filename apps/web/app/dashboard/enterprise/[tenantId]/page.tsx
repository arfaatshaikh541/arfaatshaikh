"use client";

import { use, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api, ApiError, type EnterpriseMembership, type EnterpriseTenant } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

interface AuditEvent {
  seq: number;
  occurred_at: string;
  action: string;
  actor_user_id?: string;
}

interface Entitlements {
  plan_key: string;
  plan_name: string;
  status: string;
  features: Record<string, unknown>;
}

const ADMIN_ROLES = new Set(["enterprise_owner", "enterprise_admin"]);

export default function TenantDetailPage({ params }: { params: Promise<{ tenantId: string }> }) {
  const { tenantId } = use(params);
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("application_owner");
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [inviteSent, setInviteSent] = useState(false);

  const tenant = useQuery({
    queryKey: ["tenant", tenantId],
    queryFn: () => api.get<EnterpriseTenant>(`/api/v1/enterprises/${tenantId}`),
  });

  const members = useQuery({
    queryKey: ["tenant-members", tenantId],
    queryFn: () => api.get<EnterpriseMembership[]>(`/api/v1/enterprises/${tenantId}/members`),
  });

  const entitlements = useQuery({
    queryKey: ["tenant-entitlements", tenantId],
    queryFn: () => api.get<Entitlements>(`/api/v1/enterprises/${tenantId}/subscription`),
  });

  const audit = useQuery({
    queryKey: ["tenant-audit", tenantId],
    queryFn: () => api.get<AuditEvent[]>(`/api/v1/enterprises/${tenantId}/audit`),
  });

  // This only drives which controls are shown -- the server independently
  // re-checks every permission on every request regardless of what the
  // client displays.
  const myRole = members.data?.find((m) => m.user_id === user?.user_id)?.role_key;
  const canManageUsers = !members.isError && ADMIN_ROLES.has(myRole ?? "");

  const sendInvite = async () => {
    setInviteError(null);
    setInviteSent(false);
    try {
      await api.post(`/api/v1/enterprises/${tenantId}/invitations`, {
        email: inviteEmail,
        role_key: inviteRole,
      });
      setInviteSent(true);
      setInviteEmail("");
      queryClient.invalidateQueries({ queryKey: ["tenant-audit", tenantId] });
    } catch (err) {
      setInviteError(err instanceof ApiError ? err.message : "Failed to send invitation.");
    }
  };

  if (tenant.isError && tenant.error instanceof ApiError && tenant.error.status === 403) {
    return (
      <main className="mx-auto w-full max-w-3xl flex-1 p-8">
        <p>You do not have access to this tenant.</p>
        <Link href="/dashboard" className="underline">Back to dashboard</Link>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 p-8">
      <Link href="/dashboard" className="text-sm underline">&larr; Dashboard</Link>
      <h1 className="mt-2 mb-1 text-2xl font-semibold">{tenant.data?.display_name ?? "..."}</h1>
      {tenant.data?.is_fictional_demo_data && (
        <p className="mb-4 inline-block rounded bg-amber-100 px-2 py-1 text-xs font-medium text-amber-900 dark:bg-amber-900 dark:text-amber-100">
          Fictional demo data
        </p>
      )}
      <p className="mb-6 text-sm text-zinc-500">
        {tenant.data?.country} &middot; status: {tenant.data?.status}
      </p>

      <section className="mb-8">
        <Link href={`/dashboard/enterprise/${tenantId}/policies`} className="text-sm underline">
          Sovereignty policies &rarr;
        </Link>
      </section>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-medium">Subscription</h2>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          {entitlements.data?.plan_name ?? "No active subscription"}
        </p>
      </section>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-medium">Members</h2>
        <ul className="flex flex-col gap-2">
          {members.data?.map((m) => (
            <li key={m.id} className="flex items-center justify-between rounded-lg border border-zinc-200 px-4 py-2 text-sm dark:border-zinc-800">
              <span>{m.user_id}</span>
              <span className="text-zinc-500">{m.role_name}</span>
            </li>
          ))}
        </ul>

        {canManageUsers && (
          <div className="mt-4 flex flex-col gap-2 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
            <h3 className="text-sm font-medium">Invite a user</h3>
            <input
              placeholder="email@example.com"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            />
            <select
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value)}
              className="rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            >
              <option value="enterprise_admin">Enterprise Administrator</option>
              <option value="ai_platform_engineer">AI Platform Engineer</option>
              <option value="devops_engineer">DevOps Engineer</option>
              <option value="security_administrator">Security Administrator</option>
              <option value="finops_manager">FinOps Manager</option>
              <option value="application_owner">Application Owner</option>
              <option value="read_only_auditor">Read-Only Auditor</option>
            </select>
            {inviteError && <p className="text-sm text-red-600">{inviteError}</p>}
            {inviteSent && <p className="text-sm text-green-700 dark:text-green-400">Invitation sent.</p>}
            <button
              onClick={sendInvite}
              className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white dark:bg-white dark:text-zinc-900"
            >
              Send invitation
            </button>
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-medium">Audit log</h2>
        <ul className="flex flex-col gap-1 text-sm">
          {audit.data?.map((e) => (
            <li key={e.seq} className="flex justify-between border-b border-zinc-100 py-1 dark:border-zinc-900">
              <span>{e.action}</span>
              <span className="text-zinc-500">{new Date(e.occurred_at).toLocaleString()}</span>
            </li>
          ))}
          {audit.isError && <li className="text-zinc-500">You do not have permission to view the audit log.</li>}
        </ul>
      </section>
    </main>
  );
}
