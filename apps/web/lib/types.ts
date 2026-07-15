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

// --- Milestone 2: integrations ---

export interface CatalogEntryRead {
  id: string;
  provider_id: string;
  name: string;
  category: string;
  auth_method: string;
  required_scopes: string[];
  permission_risk: string;
  supported_data_types: string[];
  sync_modes: string[];
  webhook_support: boolean;
  is_simulator: boolean;
  description: string;
}

export interface TenantIntegrationRead {
  id: string;
  provider_id: string;
  provider_name: string;
  label: string;
  status: string;
  sync_mode: string;
  last_synced_at: string | null;
  created_at: string;
}

export interface IntegrationHealthRead {
  status: string;
  message: string;
  checked_at: string;
}

export interface SyncRunRead {
  id: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  records_processed: number;
  records_created: number;
  records_updated: number;
  error_message: string | null;
}

export interface TriggerSyncResponse {
  sync_run_id: string;
  task_id: string;
}

// --- Milestone 2: assets ---

export interface AssetListItem {
  id: string;
  asset_type: string;
  display_name: string;
  source: string;
  criticality: string;
  exposure: string;
  lifecycle_status: string;
  last_observed_at: string;
}

export interface AssetIdentifierRead {
  identifier_type: string;
  identifier_value: string;
}

export interface AssetRelationshipRead {
  relationship_type: string;
  direction: "outbound" | "inbound";
  related_asset_id: string;
  related_asset_display_name: string;
  source: string;
  observed_at: string;
}

export interface AssetChangeRead {
  field_name: string;
  old_value: string | null;
  new_value: string | null;
  changed_at: string;
}

export interface AssetOwnerRead {
  user_id: string;
  email: string;
  ownership_type: string;
}

export interface AssetDetail {
  id: string;
  asset_type: string;
  display_name: string;
  source: string;
  confidence: number;
  criticality: string;
  exposure: string;
  lifecycle_status: string;
  attributes: Record<string, unknown>;
  last_observed_at: string;
  last_assessed_at: string | null;
  identifiers: AssetIdentifierRead[];
  relationships: AssetRelationshipRead[];
  owners: AssetOwnerRead[];
  tags: Record<string, string>;
}

// --- Milestone 3: findings and risk engine ---

export interface FindingListItem {
  id: string;
  rule_key: string;
  title: string;
  category: string;
  severity: string;
  status: string;
  risk_score: number;
  asset_id: string;
  asset_display_name: string;
  asset_criticality: string;
  assigned_to_user_id: string | null;
  first_observed_at: string;
  last_observed_at: string;
}

export interface FindingDetail extends FindingListItem {
  description: string;
  evidence: Record<string, unknown>;
  resolution_note: string | null;
  accepted_risk_expires_at: string | null;
  closed_at: string | null;
}

export interface FindingActivityRead {
  actor_label: string;
  action: string;
  context: Record<string, unknown>;
  created_at: string;
}

export interface RiskSummaryRead {
  security_score: number;
  open_findings_total: number;
  open_findings_by_severity: Record<string, number>;
}
