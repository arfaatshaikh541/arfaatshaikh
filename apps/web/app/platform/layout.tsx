"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { PlatformShell } from "@/components/PlatformShell";
import { useAuth } from "@/lib/auth-context";

// Hardening-programme Milestone 4 (Platform-Admin Separation): MFA is
// unconditional for platform accounts (core/deps.py:get_platform_context)
// — this is the frontend's own copy of the same redirect
// `(tenant)/layout.tsx` already does for tenant admins, pointed at the
// platform-specific enrollment page (`/platform/security`) since a
// platform-only account has no tenant membership and can't reach
// `/settings/security`, which lives under a layout that requires one.
const MFA_ENROLLMENT_PATH = "/platform/security";

export default function PlatformLayout({ children }: { children: React.ReactNode }) {
  const { isLoading, isAuthenticated, isPlatformUser, me } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const needsMfaEnrollment = Boolean(me?.mfa_enrollment_required) && pathname !== MFA_ENROLLMENT_PATH;

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    if (!isPlatformUser) {
      router.replace("/dashboard");
      return;
    }
    if (needsMfaEnrollment) {
      router.replace(MFA_ENROLLMENT_PATH);
    }
  }, [isLoading, isAuthenticated, isPlatformUser, needsMfaEnrollment, router]);

  if (isLoading || !isAuthenticated || !isPlatformUser || needsMfaEnrollment) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-ink-500">Loading…</p>
      </main>
    );
  }

  return <PlatformShell>{children}</PlatformShell>;
}
