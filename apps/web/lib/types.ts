export interface MembershipSummary {
  tenant_id: string;
  tenant_name: string;
  tenant_slug: string;
  role_name: string;
}

export interface CurrentUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  email_verified: boolean;
  is_platform_admin: boolean;
  active_tenant_id: string | null;
  memberships: MembershipSummary[];
}

export interface EntitlementsResponse {
  tenant_id: string;
  plan_code: string | null;
  subscription_status: string | null;
  modules: Record<string, boolean>;
  features: Record<string, { enabled?: boolean; limit?: number | null }>;
  role_name: string;
  permissions: string[];
  tenant_status: "active" | "suspended" | "read_only" | "archived";
}

export interface TenantSummary {
  id: string;
  name: string;
  slug: string;
  status: "active" | "suspended" | "read_only" | "archived";
  created_at: string;
}
