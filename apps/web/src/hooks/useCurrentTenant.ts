"use client";

import { useCallback, useEffect, useState } from "react";

import { getCurrentTenantId, setCurrentTenantId } from "@/lib/api-client";
import { useCurrentUser } from "@/hooks/useCurrentUser";

/**
 * Resolves the "active tenant" for the signed-in user: an explicit choice
 * persisted client-side (so a multi-tenant user can switch), falling back
 * to their first membership. This is purely a UX affordance - the backend
 * re-verifies membership on every request regardless of what the client
 * sends (see docs/architecture/tenant-isolation-strategy.md), so a stale
 * or tampered value here can only ever result in a 403/404, never a
 * cross-tenant data leak.
 */
export function useCurrentTenant() {
  const { data: user } = useCurrentUser();
  const [tenantId, setTenantIdState] = useState<string | null>(null);

  useEffect(() => {
    if (!user || user.memberships.length === 0) return;
    const stored = getCurrentTenantId();
    const validStored = user.memberships.find((m) => m.tenant_id === stored);
    const resolved = validStored?.tenant_id ?? user.memberships[0]?.tenant_id ?? null;
    if (resolved) {
      setCurrentTenantId(resolved);
      setTenantIdState(resolved);
    }
  }, [user]);

  const switchTenant = useCallback((newTenantId: string) => {
    setCurrentTenantId(newTenantId);
    setTenantIdState(newTenantId);
  }, []);

  const membership = user?.memberships.find((m) => m.tenant_id === tenantId) ?? null;

  return {
    tenantId,
    membership,
    memberships: user?.memberships ?? [],
    switchTenant,
    isReady: Boolean(tenantId),
  };
}
