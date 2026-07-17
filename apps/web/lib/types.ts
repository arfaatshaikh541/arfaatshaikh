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

export type CampaignStatus =
  | "draft"
  | "estimating"
  | "ready"
  | "queued"
  | "running"
  | "pausing"
  | "paused"
  | "cancelling"
  | "cancelled"
  | "completed"
  | "partially_completed"
  | "failed";

export type Campaign = {
  id: string;
  name: string;
  source_key: string;
  status: CampaignStatus;
  result_limit: number;
  created_at: string;
};

export type CampaignFilter = {
  industry: string;
  category: string | null;
  subcategory: string | null;
  country: string;
  region: string | null;
  city: string;
  area: string | null;
  radius_km: number | null;
  min_rating: number | null;
  min_reviews: number | null;
  must_have_phone: boolean;
  website_requirement: string;
  business_status: string | null;
};

export type CampaignDetail = Campaign & {
  filter: CampaignFilter;
  estimated_credits: number | null;
  estimated_results: number | null;
};

export type CreateCampaignRequest = {
  name: string;
  source_key: string;
  result_limit: number;
  industry: string;
  category?: string | null;
  subcategory?: string | null;
  country: string;
  region?: string | null;
  city: string;
  area?: string | null;
  radius_km?: number | null;
  min_rating?: number | null;
  min_reviews?: number | null;
  must_have_phone: boolean;
  website_requirement: string;
  business_status?: string | null;
};

export type CampaignEstimate = {
  campaign_id: string;
  estimated_credits: number;
  estimated_results: number;
  calculated_at: string;
  available_balance: number;
};

export type CampaignProgress = {
  campaign_id: string;
  status: CampaignStatus;
  job_status: string | null;
  total_tasks: number;
  succeeded_tasks: number;
  failed_tasks: number;
  pending_tasks: number;
  businesses_found: number;
};

export type CampaignEvent = {
  id: string;
  event_type: string;
  from_status: string | null;
  to_status: string | null;
  message: string | null;
  created_at: string;
};

export type CampaignErrorEntry = {
  id: string;
  error_type: string;
  message: string;
  created_at: string;
};
