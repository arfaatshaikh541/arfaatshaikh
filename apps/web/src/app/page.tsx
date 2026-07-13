"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useCurrentUser } from "@/hooks/useCurrentUser";

export default function RootPage() {
  const router = useRouter();
  const { data, isLoading, isError } = useCurrentUser();

  useEffect(() => {
    if (isLoading) return;
    if (isError || !data) {
      router.replace("/login");
    } else if (data.is_platform_super_admin) {
      router.replace("/platform");
    } else {
      router.replace("/dashboard");
    }
  }, [data, isError, isLoading, router]);

  return (
    <main className="flex min-h-screen items-center justify-center">
      <p className="text-sm text-surface-400">Loading…</p>
    </main>
  );
}
