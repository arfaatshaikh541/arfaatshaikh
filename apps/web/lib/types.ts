import type { Permission, TenantRole, TenantStatus } from "@gridkeep/security-contracts";

export interface UserRead {
  id: string;
  email: string;
  full_name: string;
  email_verified: boolean;
  mfa_enabled: boolean;
}

export interface MembershipSummary {
  membership_id: string;
  tenant_id: string;
  tenant_name: string;
  tenant_slug: string;
  tenant_status: TenantStatus;
  role_name: TenantRole;
}

export interface LoginResponse {
  user: UserRead;
  memberships: MembershipSummary[];
  active_membership_id: string | null;
  csrf_token: string;
}

export interface MeResponse {
  user: UserRead;
  memberships: MembershipSummary[];
  active_membership_id: string | null;
}

export interface TenantRead {
  id: string;
  name: string;
  slug: string;
  status: TenantStatus;
  industry: string | null;
  is_demo: boolean;
}

export interface EntitlementsRead {
  entitled_modules: string[];
  entitled_features: string[];
  feature_limits: Record<string, number>;
}

export interface SubscriptionRead {
  plan_key: string;
  plan_name: string;
  status: string;
  trial_ends_at: string | null;
  current_period_end: string | null;
}

export interface MembershipRead {
  id: string;
  user_id: string;
  email: string;
  full_name: string;
  role_name: TenantRole;
  status: string;
}

export interface RoleRead {
  id: string;
  name: TenantRole;
  is_platform_role: boolean;
}

/** Derives the effective permission set client-side from role name using
 * the same DEFAULT_ROLE_PERMISSIONS table the backend seeds from — used
 * only to drive which UI affordances render; the backend re-checks every
 * permission on every request regardless of what the UI shows. */
export type { Permission };
