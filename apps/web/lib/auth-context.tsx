"use client";

import { DEFAULT_ROLE_PERMISSIONS, type Permission } from "@gridkeep/security-contracts";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, type ReactNode } from "react";

import { apiClient, ApiError } from "./api-client";
import type { MeResponse } from "./types";

interface AuthContextValue {
  me: MeResponse | undefined;
  isLoading: boolean;
  isAuthenticated: boolean;
  activeMembership: MeResponse["memberships"][number] | undefined;
  permissions: ReadonlySet<Permission>;
  hasPermission: (permission: Permission) => boolean;
  refetch: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const { data, isLoading, refetch } = useQuery<MeResponse | null>({
    queryKey: ["auth", "me"],
    queryFn: async () => {
      try {
        return await apiClient.get<MeResponse>("/api/auth/me");
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) return null;
        throw err;
      }
    },
  });

  const activeMembership = data?.memberships.find(
    (m) => m.membership_id === data.active_membership_id,
  );
  const permissions = new Set<Permission>(
    activeMembership ? DEFAULT_ROLE_PERMISSIONS[activeMembership.role_name] ?? [] : [],
  );

  const value: AuthContextValue = {
    me: data ?? undefined,
    isLoading,
    isAuthenticated: Boolean(data),
    activeMembership,
    permissions,
    hasPermission: (permission) => permissions.has(permission),
    refetch,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function useInvalidateAuth() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
}
