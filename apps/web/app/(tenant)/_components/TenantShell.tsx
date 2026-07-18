"use client";

import { Button } from "@gridkeep/ui";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/campaigns", label: "Campaigns" },
  { href: "/leads", label: "Leads" },
  { href: "/team", label: "Team" },
  { href: "/usage", label: "Usage & Billing" },
  { href: "/audit", label: "Audit Log" },
];

export function TenantShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { data: session } = useSession();

  const activeTenant = session?.memberships.find((m) => m.tenant_id === session.active_tenant_id);

  const handleLogout = async () => {
    await api.post("/auth/logout");
    queryClient.clear();
    router.push("/login");
  };

  return (
    <div className="flex min-h-screen bg-slate-50 dark:bg-slate-950">
      <aside className="hidden w-64 flex-col border-r border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900 sm:flex">
        <div className="mb-6 px-2">
          <p className="text-lg font-semibold text-brand-700 dark:text-brand-400">GRIDKEEP</p>
          {activeTenant && (
            <p className="truncate text-xs text-slate-500 dark:text-slate-400">{activeTenant.tenant_name}</p>
          )}
        </div>
        <nav className="flex flex-1 flex-col gap-1">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`rounded-md px-3 py-2 text-sm font-medium ${
                  isActive
                    ? "bg-brand-50 text-brand-700 dark:bg-brand-900/30 dark:text-brand-300"
                    : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-slate-200 pt-4 dark:border-slate-800">
          <p className="truncate px-2 text-xs text-slate-500 dark:text-slate-400">{session?.user.email}</p>
          <Button variant="ghost" className="mt-1 w-full justify-start" onClick={handleLogout}>
            Sign out
          </Button>
        </div>
      </aside>
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
