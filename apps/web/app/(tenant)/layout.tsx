"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useSession } from "@/lib/session";
import { TenantShell } from "./_components/TenantShell";

export default function TenantLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { data: session, isLoading, isError } = useSession();

  useEffect(() => {
    if (isLoading) return;
    if (isError || !session) {
      router.replace("/login");
      return;
    }
    if (!session.active_tenant_id) {
      router.replace("/onboarding");
    }
  }, [isLoading, isError, session, router]);

  if (isLoading || !session || !session.active_tenant_id) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-950">
        <p className="text-sm text-slate-500">Loading your workspace...</p>
      </div>
    );
  }

  return <TenantShell>{children}</TenantShell>;
}
