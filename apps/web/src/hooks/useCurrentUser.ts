"use client";

import type { CurrentUser } from "@leadflow/shared-types";
import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";

export function useCurrentUser() {
  return useQuery({
    queryKey: ["current-user"],
    queryFn: () => apiFetch<CurrentUser>("/auth/me", { withTenant: false }),
    retry: false,
  });
}
