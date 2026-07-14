"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

export default function RootPage() {
  const router = useRouter();
  const { user, isLoading, isError } = useAuth();

  useEffect(() => {
    if (isLoading) return;
    if (isError || !user) {
      router.replace("/login");
      return;
    }
    if (user.is_platform_admin && user.memberships.length === 0) {
      router.replace("/admin");
      return;
    }
    router.replace("/dashboard");
  }, [isLoading, isError, user, router]);

  return null;
}
