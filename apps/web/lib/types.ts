/**
 * Hand-written types mirroring the API's Pydantic response schemas
 * (see the schemas.py file in each apps/api module). A generated-from-
 * OpenAPI variant can replace this once the API surface stabilizes
 * beyond Milestone 1.
 */

export type User = {
  id: string;
  email: string;
  full_name: string;
  email_verified: boolean;
  mfa_enabled: boolean;
};

export type MembershipSummary = {
  tenant_id: string;
  tenant_name: string;
  tenant_slug: string;
  tenant_status: string;
  role_name: string;
};

export type SessionInfo = {
  user: User;
  active_tenant_id: string | null;
  memberships: MembershipSummary[];
};

export type Tenant = {
  id: string;
  name: string;
  slug: string;
  status: string;
};

export type Role = {
  id: string;
  name: string;
  description: string | null;
};

export type Invitation = {
  id: string;
  email: string;
  role_id: string;
  status: string;
  expires_at: string;
};

export type WalletBalance = {
  tenant_id: string;
  balance: number;
  available: number;
};

export type CreditTransaction = {
  id: string;
  amount: number;
  type: string;
  reference: string | null;
  created_at: string;
};

export type Subscription = {
  tenant_id: string;
  plan_key: string;
  plan_name: string;
  status: string;
  current_period_start: string;
  current_period_end: string;
  entitlements: Record<string, unknown>;
};

export type AuditLogEntry = {
  id: string;
  actor_user_id: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
};
