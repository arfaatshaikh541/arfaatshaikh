"use client";

import { Button } from "@leadflow/ui";
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { apiFetch } from "@/lib/api-client";
import { useCurrentTenant } from "@/hooks/useCurrentTenant";
import { useCurrentUser } from "@/hooks/useCurrentUser";

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/leads", label: "Leads" },
  { href: "/leads/board", label: "Pipeline board" },
  { href: "/services", label: "Services" },
  { href: "/qualification-form", label: "Qualification Form" },
  { href: "/pipeline", label: "Pipeline Stages" },
  { href: "/team", label: "Team" },
  { href: "/settings", label: "Settings" },
];

export function TenantShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const { data: user, isLoading, isError } = useCurrentUser();
  const { tenantId, membership, memberships, switchTenant, isReady } = useCurrentTenant();

  useEffect(() => {
    if (!isLoading && (isError || !user)) {
      router.replace("/login");
    }
  }, [isError, isLoading, router, user]);

  const handleLogout = async () => {
    await apiFetch("/auth/logout", { method: "POST", withTenant: false });
    queryClient.clear();
    router.replace("/login");
  };

  if (isLoading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-surface-400">Loading…</p>
      </div>
    );
  }

  if (memberships.length === 0) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <div className="max-w-md rounded-lg border border-surface-800 bg-surface-900 p-6 text-center">
          <p className="text-surface-200">
            Your account isn&apos;t a member of any workspace yet. Ask a tenant administrator to
            invite you.
          </p>
          <Button variant="secondary" className="mt-4" onClick={handleLogout}>
            Sign out
          </Button>
        </div>
      </div>
    );
  }

  if (!isReady) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-surface-400">Loading workspace…</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-56 flex-shrink-0 flex-col border-r border-surface-800 bg-surface-900 px-4 py-6">
        <span className="mb-8 px-2 text-base font-semibold text-surface-50">
          Lead<span className="text-accent-500">Flow</span>
        </span>
        <nav className="flex flex-col gap-1">
          {NAV.map((item) => {
            const active = pathname?.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={
                  "rounded-md px-2.5 py-2 text-sm font-medium transition-colors " +
                  (active
                    ? "bg-accent-600/10 text-accent-400"
                    : "text-surface-300 hover:bg-surface-800 hover:text-surface-100")
                }
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>
      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-surface-800 bg-surface-950 px-6 py-3">
          <div className="flex items-center gap-2">
            {memberships.length > 1 ? (
              <select
                value={tenantId ?? ""}
                onChange={(e) => switchTenant(e.target.value)}
                className="rounded-md border border-surface-700 bg-surface-900 px-2 py-1 text-sm text-surface-100"
                aria-label="Switch workspace"
              >
                {memberships.map((m) => (
                  <option key={m.tenant_id} value={m.tenant_id}>
                    {m.tenant_name}
                  </option>
                ))}
              </select>
            ) : (
              <span className="text-sm font-medium text-surface-200">
                {memberships[0]?.tenant_name}
              </span>
            )}
            {membership ? (
              <span className="rounded-full bg-surface-800 px-2 py-0.5 text-xs text-surface-400">
                {membership.role.name}
              </span>
            ) : null}
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-surface-400">
              {user.first_name} {user.last_name}
            </span>
            <Button variant="ghost" onClick={handleLogout}>
              Sign out
            </Button>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}
