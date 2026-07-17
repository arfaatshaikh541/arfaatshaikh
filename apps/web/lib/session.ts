"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import type { SessionInfo } from "./types";

export function useSession() {
  return useQuery<SessionInfo>({
    queryKey: ["session"],
    queryFn: () => api.get<SessionInfo>("/auth/session"),
    retry: false,
    staleTime: 30_000,
  });
}
