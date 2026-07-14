"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api-client";
import { useAuth, useInvalidateAuth } from "@/lib/auth-context";
import { useEntitlements } from "@/lib/entitlements";
import { TenantSwitcher } from "./tenant-switcher";

const NAV_ITEMS: { href: string; label: string; permission?: string; module?: string }[] = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/leads", label: "Leads", permission: "leads.view", module: "crm" },
  { href: "/services", label: "Services", permission: "services.manage", module: "lead_capture" },
  { href: "/qualification-forms", label: "Qualification Forms", permission: "services.manage", module: "lead_capture" },
  { href: "/users", label: "Users", permission: "users.manage" },
  { href: "/roles", label: "Roles", permission: "roles.manage" },
  { href: "/subscription", label: "Subscription", permission: "subscriptions.view" },
  { href: "/settings", label: "Settings", permission: "settings.manage" },
];

export function TenantSidebar() {
  const pathname = usePathname();
  const { user } = useAuth();
  const { data: entitlements } = useEntitlements();
  const invalidateAuth = useInvalidateAuth();
  const router = useRouter();

  const logout = useMutation({
    mutationFn: () => api.post("/auth/logout"),
    onSuccess: async () => {
      await invalidateAuth();
      router.replace("/login");
    },
  });

  const visibleItems = NAV_ITEMS.filter((item) => {
    if (item.permission && !entitlements?.permissions.includes(item.permission)) return false;
    if (item.module && !entitlements?.modules[item.module]) return false;
    return true;
  });

  return (
    <aside className="flex h-screen w-60 flex-none flex-col border-r border-surface-border bg-surface-raised">
      <div className="border-b border-surface-border p-4">
        <span className="text-sm font-semibold tracking-tight text-ink">
          Client <span className="text-accent">Ops</span>
        </span>
        <div className="mt-3">
          <TenantSwitcher />
        </div>
      </div>
      <nav className="flex-1 space-y-0.5 p-3">
        {visibleItems.map((item) => {
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
        {user?.is_platform_admin && (
          <Link
            href="/admin"
            className="focus-ring mt-4 block rounded-md border border-surface-border px-3 py-2 text-sm text-ink-muted hover:text-ink"
          >
            Platform Admin →
          </Link>
        )}
      </nav>
      <div className="border-t border-surface-border p-3">
        <p className="truncate px-1 text-xs text-ink-faint">{user?.email}</p>
        <button
          onClick={() => logout.mutate()}
          className="focus-ring mt-2 w-full rounded-md px-3 py-2 text-left text-sm text-ink-muted hover:bg-surface hover:text-ink"
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}
