"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { AppShell } from "@/components/AppShell";
import { useAuth } from "@/lib/auth-context";

const MFA_ENROLLMENT_PATH = "/settings/security";

export default function TenantLayout({ children }: { children: React.ReactNode }) {
  const { isLoading, isAuthenticated, me } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const needsMfaEnrollment = Boolean(me?.mfa_enrollment_required) && pathname !== MFA_ENROLLMENT_PATH;

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    if (me && !me.active_membership_id) {
      router.replace("/select-workspace");
      return;
    }
    if (needsMfaEnrollment) {
      router.replace(MFA_ENROLLMENT_PATH);
    }
  }, [isLoading, isAuthenticated, me, needsMfaEnrollment, router]);

  if (isLoading || !isAuthenticated || !me?.active_membership_id || needsMfaEnrollment) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-ink-500">Loading…</p>
      </main>
    );
  }

  return <AppShell>{children}</AppShell>;
}
