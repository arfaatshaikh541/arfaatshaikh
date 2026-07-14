"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Alert } from "@/components/ui/alert";
import { TenantSidebar } from "@/components/tenant-sidebar";
import { useAuth } from "@/lib/auth-context";
import { useEntitlements } from "@/lib/entitlements";

export default function TenantAppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { user, isLoading, isError } = useAuth();
  const { data: entitlements } = useEntitlements();

  useEffect(() => {
    if (isLoading) return;
    if (isError || !user) {
      router.replace("/login");
      return;
    }
    if (!user.active_tenant_id) {
      router.replace("/login");
    }
  }, [isLoading, isError, user, router]);

  if (isLoading || !user || !user.active_tenant_id) {
    return <div className="flex h-screen items-center justify-center text-ink-muted">Loading…</div>;
  }

  return (
    <div className="flex h-screen bg-surface">
      <TenantSidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-5xl px-8 py-8">
          {entitlements?.tenant_status === "read_only" && (
            <div className="mb-6">
              <Alert tone="warning">
                This workspace is in read-only mode. Changes are disabled until your subscription is restored.
              </Alert>
            </div>
          )}
          {entitlements?.tenant_status === "suspended" && (
            <div className="mb-6">
              <Alert tone="error">This workspace is suspended. Contact your administrator.</Alert>
            </div>
          )}
          {children}
        </div>
      </main>
    </div>
  );
}
