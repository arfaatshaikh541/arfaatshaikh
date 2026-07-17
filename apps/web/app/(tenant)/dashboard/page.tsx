"use client";

import { Card } from "@gridkeep/ui";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { Subscription, WalletBalance } from "@/lib/types";

export default function DashboardPage() {
  const { data: session } = useSession();
  const activeTenant = session?.memberships.find((m) => m.tenant_id === session.active_tenant_id);

  const { data: wallet } = useQuery<WalletBalance>({
    queryKey: ["wallet"],
    queryFn: () => api.get<WalletBalance>("/usage/wallet"),
  });

  const { data: subscription } = useQuery<Subscription>({
    queryKey: ["subscription"],
    queryFn: () => api.get<Subscription>("/billing/subscription"),
    retry: false,
  });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">{activeTenant?.tenant_name ?? "Dashboard"}</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          You&apos;re signed in as <strong>{activeTenant?.role_name}</strong>.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <p className="text-sm text-slate-500 dark:text-slate-400">Available credits</p>
          <p className="mt-1 text-2xl font-semibold">{wallet ? wallet.available.toLocaleString() : "—"}</p>
        </Card>
        <Card>
          <p className="text-sm text-slate-500 dark:text-slate-400">Plan</p>
          <p className="mt-1 text-2xl font-semibold">{subscription?.plan_name ?? "—"}</p>
        </Card>
        <Card>
          <p className="text-sm text-slate-500 dark:text-slate-400">Workspace status</p>
          <p className="mt-1 text-2xl font-semibold capitalize">{activeTenant?.tenant_status ?? "—"}</p>
        </Card>
      </div>

      <Card>
        <h2 className="mb-2 text-lg font-medium">Getting started</h2>
        <p className="text-sm text-slate-600 dark:text-slate-300">
          Start a <Link href="/campaigns" className="font-medium text-brand-700 hover:underline dark:text-brand-400">lead-discovery campaign</Link>,
          invite your team from the <strong>Team</strong> page, and review your plan and credit
          history under <strong>Usage &amp; Billing</strong>.
        </p>
      </Card>
    </div>
  );
}
