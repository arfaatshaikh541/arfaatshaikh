"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { AppShell } from "@/components/AppShell";
import { useAuth } from "@/lib/auth-context";

export default function TenantLayout({ children }: { children: React.ReactNode }) {
  const { isLoading, isAuthenticated, me } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    if (me && !me.active_membership_id) {
      router.replace("/select-workspace");
    }
  }, [isLoading, isAuthenticated, me, router]);

  if (isLoading || !isAuthenticated || !me?.active_membership_id) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-ink-500">Loading…</p>
      </main>
    );
  }

  return <AppShell>{children}</AppShell>;
}
