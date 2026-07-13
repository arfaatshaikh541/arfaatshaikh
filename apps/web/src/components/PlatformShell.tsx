"use client";

import { Button } from "@leadflow/ui";
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { apiFetch } from "@/lib/api-client";
import { useCurrentUser } from "@/hooks/useCurrentUser";

const NAV = [
  { href: "/platform", label: "Overview" },
  { href: "/platform/tenants", label: "Tenants" },
  { href: "/platform/plans", label: "Plans" },
];

export function PlatformShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const { data: user, isLoading, isError } = useCurrentUser();

  useEffect(() => {
    if (isLoading) return;
    if (isError || !user) {
      router.replace("/login");
      return;
    }
    if (!user.is_platform_super_admin) {
      router.replace("/dashboard");
    }
  }, [isError, isLoading, router, user]);

  const handleLogout = async () => {
    await apiFetch("/auth/logout", { method: "POST", withTenant: false });
    queryClient.clear();
    router.replace("/login");
  };

  if (isLoading || !user || !user.is_platform_super_admin) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-surface-400">Loading…</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-56 flex-shrink-0 flex-col border-r border-surface-800 bg-surface-900 px-4 py-6">
        <span className="mb-1 px-2 text-base font-semibold text-surface-50">
          Lead<span className="text-accent-500">Flow</span>
        </span>
        <span className="mb-8 px-2 text-xs uppercase tracking-wide text-surface-500">
          Platform Admin
        </span>
        <nav className="flex flex-col gap-1">
          {NAV.map((item) => {
            const active = pathname === item.href;
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
          <span className="text-sm font-medium text-surface-200">Platform administration</span>
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
