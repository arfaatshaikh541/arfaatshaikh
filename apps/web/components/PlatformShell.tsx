"use client";

import { Button } from "@gridkeep/ui";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";

import { apiClient } from "@/lib/api-client";
import { useAuth, useInvalidateAuth } from "@/lib/auth-context";

const NAV_ITEMS = [
  { href: "/platform/tenants", label: "Tenants" },
  { href: "/platform/audit-logs", label: "Audit Log" },
];

export function PlatformShell({ children }: { children: ReactNode }) {
  const { me } = useAuth();
  const invalidateAuth = useInvalidateAuth();
  const router = useRouter();
  const pathname = usePathname();

  const logout = async () => {
    await apiClient.post("/api/auth/logout");
    invalidateAuth();
    router.replace("/login");
  };

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-60 flex-col border-r border-surface-border bg-surface-900 p-4">
        <div className="mb-6 flex items-center gap-2 text-sm font-semibold text-ink-900">
          <span className="h-2.5 w-2.5 rounded-full bg-accent" aria-hidden="true" />
          GRIDKEEP Platform
        </div>
        <nav className="flex flex-col gap-1" aria-label="Primary">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href || pathname?.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={isActive ? "page" : undefined}
                className={[
                  "rounded px-3 py-2 text-sm",
                  isActive
                    ? "bg-surface-700 text-ink-900"
                    : "text-ink-500 hover:bg-surface-800 hover:text-ink-700",
                ].join(" ")}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>
      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-surface-border bg-surface-900 px-6 py-3">
          <div className="text-sm text-ink-500">
            {me?.user.platform_role_name ? (
              <span className="font-medium text-ink-900">
                {me.user.platform_role_name.replace(/_/g, " ")}
              </span>
            ) : null}
          </div>
          <div className="flex items-center gap-3 text-sm text-ink-500">
            <span>{me?.user.email}</span>
            <Button size="sm" variant="ghost" onClick={logout}>
              Sign out
            </Button>
          </div>
        </header>
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
