"use client";

import Link from "next/link";
import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { useAuth, useInvalidateAuth } from "@/lib/auth-context";

const NAV_ITEMS = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/tenants", label: "Tenants" },
  { href: "/admin/plans", label: "Plans" },
  { href: "/admin/modules", label: "Modules" },
  { href: "/admin/add-ons", label: "Add-ons" },
  { href: "/admin/usage-metrics", label: "Usage metrics" },
  { href: "/admin/audit-logs", label: "Audit logs" },
];

export default function PlatformAdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, isLoading, isError } = useAuth();
  const invalidateAuth = useInvalidateAuth();

  useEffect(() => {
    if (isLoading) return;
    if (isError || !user) {
      router.replace("/login");
      return;
    }
    if (!user.is_platform_admin) {
      router.replace("/dashboard");
    }
  }, [isLoading, isError, user, router]);

  const logout = useMutation({
    mutationFn: () => api.post("/auth/logout"),
    onSuccess: async () => {
      await invalidateAuth();
      router.replace("/login");
    },
  });

  if (isLoading || !user?.is_platform_admin) {
    return <div className="flex h-screen items-center justify-center text-ink-muted">Loading…</div>;
  }

  return (
    <div className="flex h-screen bg-surface">
      <aside className="flex h-screen w-60 flex-none flex-col border-r border-surface-border bg-surface-raised">
        <div className="border-b border-surface-border p-4">
          <span className="text-sm font-semibold tracking-tight text-ink">
            Platform <span className="text-accent">Admin</span>
          </span>
        </div>
        <nav className="flex-1 space-y-0.5 p-3">
          {NAV_ITEMS.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`focus-ring block rounded-md px-3 py-2 text-sm transition-colors ${
                  active ? "bg-accent/15 text-accent" : "text-ink-muted hover:bg-surface hover:text-ink"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
          {user.memberships.length > 0 && (
            <Link
              href="/dashboard"
              className="focus-ring mt-4 block rounded-md border border-surface-border px-3 py-2 text-sm text-ink-muted hover:text-ink"
            >
              ← Back to workspace
            </Link>
          )}
        </nav>
        <div className="border-t border-surface-border p-3">
          <p className="truncate px-1 text-xs text-ink-faint">{user.email}</p>
          <button
            onClick={() => logout.mutate()}
            className="focus-ring mt-2 w-full rounded-md px-3 py-2 text-left text-sm text-ink-muted hover:bg-surface hover:text-ink"
          >
            Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-6xl px-8 py-8">{children}</div>
      </main>
    </div>
  );
}
