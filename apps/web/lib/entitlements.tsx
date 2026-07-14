"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api-client";
import type { EntitlementsResponse } from "./types";

/**
 * The single source of truth the UI consults to decide what to render.
 * This is a UX convenience only — every corresponding API route
 * independently re-checks module/feature/permission entitlements on the
 * backend, so hiding something here never substitutes for real
 * authorization.
 */
export function useEntitlements() {
  return useQuery({
    queryKey: ["entitlements"],
    queryFn: () => api.get<EntitlementsResponse>("/me/entitlements"),
    retry: false,
  });
}

export function useInvalidateEntitlements() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["entitlements"] });
}

export function RequireModule({
  code,
  children,
  fallback = null,
}: {
  code: string;
  children: React.ReactNode;
  fallback?: React.ReactNode;
}) {
  const { data, isLoading } = useEntitlements();
  if (isLoading) return null;
  if (!data?.modules[code]) return <>{fallback}</>;
  return <>{children}</>;
}

export function RequirePermission({
  code,
  children,
  fallback = null,
}: {
  code: string;
  children: React.ReactNode;
  fallback?: React.ReactNode;
}) {
  const { data, isLoading } = useEntitlements();
  if (isLoading) return null;
  if (!data?.permissions.includes(code)) return <>{fallback}</>;
  return <>{children}</>;
}
