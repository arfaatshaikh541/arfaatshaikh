"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api-client";
import { useAuth, useInvalidateAuth } from "@/lib/auth-context";
import { useInvalidateEntitlements } from "@/lib/entitlements";
import type { CurrentUser } from "@/lib/types";

export function TenantSwitcher() {
  const { user } = useAuth();
  const invalidateAuth = useInvalidateAuth();
  const invalidateEntitlements = useInvalidateEntitlements();
  const router = useRouter();

  const mutation = useMutation({
    mutationFn: (tenant_id: string) => api.post<CurrentUser>("/auth/switch-tenant", { tenant_id }),
    onSuccess: async () => {
      await Promise.all([invalidateAuth(), invalidateEntitlements()]);
      router.replace("/dashboard");
    },
  });

  if (!user || user.memberships.length <= 1) return null;

  return (
    <select
      className="focus-ring w-full rounded-md border border-surface-border bg-surface px-2.5 py-1.5 text-sm text-ink"
      value={user.active_tenant_id ?? ""}
      onChange={(event) => mutation.mutate(event.target.value)}
    >
      {user.memberships.map((membership) => (
        <option key={membership.tenant_id} value={membership.tenant_id}>
          {membership.tenant_name}
        </option>
      ))}
    </select>
  );
}
