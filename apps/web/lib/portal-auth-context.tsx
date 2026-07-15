"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext } from "react";
import { api } from "./api-client";
import type { CurrentPortalAccount } from "./types";

interface PortalAuthContextValue {
  account: CurrentPortalAccount | undefined;
  isLoading: boolean;
  isError: boolean;
  refetch: () => Promise<unknown>;
}

const PortalAuthContext = createContext<PortalAuthContextValue | undefined>(undefined);

export function PortalAuthProvider({ children }: { children: React.ReactNode }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["portal-auth", "me"],
    queryFn: () => api.get<CurrentPortalAccount>("/portal/auth/me"),
    retry: false,
  });

  return (
    <PortalAuthContext.Provider value={{ account: data, isLoading, isError, refetch }}>{children}</PortalAuthContext.Provider>
  );
}

export function usePortalAuth(): PortalAuthContextValue {
  const ctx = useContext(PortalAuthContext);
  if (!ctx) {
    throw new Error("usePortalAuth must be used within a PortalAuthProvider");
  }
  return ctx;
}

export function useInvalidatePortalAuth() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["portal-auth"] });
}
