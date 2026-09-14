"use client";

import type { AuthResponse, User } from "@world-of-islam/shared-types";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { apiFetch, setCsrfToken } from "@/lib/api";

type AuthState = { user: User | null; loading: boolean; login(email: string, password: string): Promise<void>; logout(): Promise<void>; refresh(): Promise<void> };
const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const auth = await apiFetch<AuthResponse>("/auth/csrf");
      setCsrfToken(auth.csrf_token);
      setUser(auth.user);
    } catch {
      setCsrfToken(null);
      setUser(null);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const login = useCallback(async (email: string, password: string) => {
    const auth = await apiFetch<AuthResponse>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
    setCsrfToken(auth.csrf_token); setUser(auth.user);
  }, []);

  const logout = useCallback(async () => {
    await apiFetch<{message:string}>("/auth/logout", { method: "POST" });
    setCsrfToken(null); setUser(null);
  }, []);

  const value = useMemo(() => ({ user, loading, login, logout, refresh }), [user, loading, login, logout, refresh]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
