"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { PlatformShell } from "@/components/PlatformShell";
import { useAuth } from "@/lib/auth-context";

export default function PlatformLayout({ children }: { children: React.ReactNode }) {
  const { isLoading, isAuthenticated, isPlatformUser } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    if (!isPlatformUser) {
      router.replace("/dashboard");
    }
  }, [isLoading, isAuthenticated, isPlatformUser, router]);

  if (isLoading || !isAuthenticated || !isPlatformUser) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-ink-500">Loading…</p>
      </main>
    );
  }

  return <PlatformShell>{children}</PlatformShell>;
}
