"use client";

import { use, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

interface Operator {
  id: string;
  legal_name: string;
  display_name: string;
  country: string;
  status: string;
  trust_level: string;
  is_fictional_demo_data: boolean;
}

interface OperatorMembership {
  id: string;
  user_id: string;
  operator_id: string;
  role_key: string;
  role_name: string;
}

interface AuditEvent {
  seq: number;
  occurred_at: string;
  action: string;
}

export default function OperatorDetailPage({ params }: { params: Promise<{ operatorId: string }> }) {
  const { operatorId } = use(params);
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("operator_support_engineer");
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [inviteSent, setInviteSent] = useState(false);

  const operator = useQuery({
    queryKey: ["operator", operatorId],
    queryFn: () => api.get<Operator>(`/api/v1/operators/${operatorId}`),
  });

  const members = useQuery({
    queryKey: ["operator-members", operatorId],
    queryFn: () => api.get<OperatorMembership[]>(`/api/v1/operators/${operatorId}/members`),
  });

  const audit = useQuery({
    queryKey: ["operator-audit", operatorId],
    queryFn: () => api.get<AuditEvent[]>(`/api/v1/operators/${operatorId}/audit`),
  });

  const myRole = members.data?.find((m) => m.user_id === user?.user_id)?.role_key;
  const canManageUsers = !members.isError && myRole === "operator_platform_owner";

  const sendInvite = async () => {
    setInviteError(null);
    setInviteSent(false);
    try {
      await api.post(`/api/v1/operators/${operatorId}/invitations`, {
        email: inviteEmail,
        role_key: inviteRole,
      });
      setInviteSent(true);
      setInviteEmail("");
      queryClient.invalidateQueries({ queryKey: ["operator-audit", operatorId] });
    } catch (err) {
      setInviteError(err instanceof ApiError ? err.message : "Failed to send invitation.");
    }
  };

  if (operator.isError && operator.error instanceof ApiError && operator.error.status === 403) {
    return (
      <main className="mx-auto w-full max-w-3xl flex-1 p-8">
        <p>You do not have access to this operator.</p>
        <Link href="/dashboard" className="underline">Back to dashboard</Link>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 p-8">
      <Link href="/dashboard" className="text-sm underline">&larr; Dashboard</Link>
      <h1 className="mt-2 mb-1 text-2xl font-semibold">{operator.data?.display_name ?? "..."}</h1>
      {operator.data?.is_fictional_demo_data && (
        <p className="mb-4 inline-block rounded bg-amber-100 px-2 py-1 text-xs font-medium text-amber-900 dark:bg-amber-900 dark:text-amber-100">
          Fictional demo data
        </p>
      )}
      <p className="mb-2 text-sm text-zinc-500">
        {operator.data?.country} &middot; status: {operator.data?.status} &middot; trust:{" "}
        {operator.data?.trust_level}
      </p>
      <Link href={`/dashboard/operator/${operatorId}/infrastructure`} className="mb-2 inline-block text-sm underline">
        Infrastructure registry &rarr;
      </Link>
      <Link href={`/dashboard/operator/${operatorId}/capacity`} className="mb-2 inline-block text-sm underline">
        Capacity offers &amp; reservations &rarr;
      </Link>
      <Link href={`/dashboard/operator/${operatorId}/cluster-agents`} className="mb-2 inline-block text-sm underline">
        Cluster agents &rarr;
      </Link>
      <Link href={`/dashboard/operator/${operatorId}/deployments`} className="mb-2 inline-block text-sm underline">
        Deployments &rarr;
      </Link>
      <Link href={`/dashboard/operator/${operatorId}/attestation`} className="mb-2 inline-block text-sm underline">
        Confidential-computing attestation &rarr;
      </Link>
      <Link href={`/dashboard/operator/${operatorId}/network-services`} className="mb-2 inline-block text-sm underline">
        Network service offers &amp; reservations &rarr;
      </Link>
      <Link href={`/dashboard/operator/${operatorId}/assurance`} className="mb-6 inline-block text-sm underline">
        Service assurance &rarr;
      </Link>

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
              <option value="operator_infrastructure_administrator">Infrastructure Administrator</option>
              <option value="operator_security_administrator">Security Administrator</option>
              <option value="operator_capacity_manager">Capacity Manager</option>
              <option value="operator_finance_manager">Finance Manager</option>
              <option value="operator_support_engineer">Support Engineer</option>
              <option value="operator_auditor">Auditor</option>
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
