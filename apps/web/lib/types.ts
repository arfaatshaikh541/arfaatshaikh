import type { Permission, PlatformRole, TenantRole, TenantStatus } from "@gridkeep/security-contracts";

export interface UserRead {
  id: string;
  email: string;
  full_name: string;
  email_verified: boolean;
  mfa_enabled: boolean;
  is_platform_user: boolean;
  platform_role_name: PlatformRole | null;
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
  mfa_enrollment_required: boolean;
}

export interface MeResponse {
  user: UserRead;
  memberships: MembershipSummary[];
  active_membership_id: string | null;
  mfa_enrollment_required: boolean;
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

// --- Milestone 4: cyber autopilot (actions, playbooks, automation) ---

export interface ActionCatalogEntry {
  action_key: string;
  name: string;
  safety_class: number;
  reversible: boolean;
}

export interface ActionRunRead {
  id: string;
  action_key: string;
  provider_id: string;
  safety_class: number;
  status: string;
  trigger: string;
  asset_id: string;
  asset_display_name: string;
  finding_id: string | null;
  playbook_id: string | null;
  params: Record<string, unknown>;
  result_message: string | null;
  requested_at: string;
  decided_at: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface RunActionResponse {
  action_run: ActionRunRead;
  task_id: string | null;
}

export interface PlaybookRead {
  id: string;
  name: string;
  description: string;
  rule_key: string;
  action_key: string;
  is_enabled: boolean;
  created_at: string;
}

export interface AutomationSettingRead {
  mode: string;
}

// --- Milestone 5: incident response ---

export interface LinkedFindingRead {
  id: string;
  title: string;
  rule_key: string;
  severity: string;
  status: string;
  asset_display_name: string;
}

export interface LinkedAssetRead {
  id: string;
  display_name: string;
  asset_type: string;
  criticality: string;
}

export interface IncidentListItem {
  id: string;
  title: string;
  severity: string;
  status: string;
  assigned_to_user_id: string | null;
  finding_count: number;
  asset_count: number;
  declared_at: string;
  resolved_at: string | null;
  closed_at: string | null;
}

export interface IncidentDetail extends IncidentListItem {
  description: string;
  declared_by_user_id: string | null;
  closure_summary: string | null;
  findings: LinkedFindingRead[];
  assets: LinkedAssetRead[];
}

export interface IncidentActivityRead {
  actor_label: string;
  action: string;
  context: Record<string, unknown>;
  created_at: string;
}

export interface IncidentSummaryRead {
  open_incidents_total: number;
  open_incidents_by_severity: Record<string, number>;
}

// --- Milestone 6: backup and ransomware resilience ---

export interface BackupJobSummary {
  asset_id: string;
  job_name: string;
  last_run_status: string | null;
  last_run_at: string | null;
  immutable: boolean | null;
  is_stale: boolean;
  score: number;
}

export interface ResilienceSummaryRead {
  recovery_confidence_score: number | null;
  backup_job_total: number;
  backup_jobs_immutable: number;
  backup_jobs_stale: number;
  backup_jobs_failed: number;
  jobs: BackupJobSummary[];
}

// --- Milestone 7: compliance and evidence ---

export interface ControlRead {
  id: string;
  key: string;
  title: string;
  description: string;
  status: string;
  note: string | null;
  updated_by_user_id: string | null;
  updated_at: string | null;
}

export interface FrameworkRead {
  id: string;
  key: string;
  name: string;
  description: string;
  score: number;
  controls: ControlRead[];
}

export interface FrameworkScoreRead {
  id: string;
  key: string;
  name: string;
  score: number;
  met_count: number;
  total_count: number;
}

export interface ComplianceSummaryRead {
  overall_score: number | null;
  frameworks: FrameworkScoreRead[];
}

export interface EvidenceRead {
  id: string;
  title: string;
  description: string;
  evidence_type: string;
  source_url: string | null;
  target_type: string;
  target_id: string;
  collected_at: string;
  created_by_user_id: string | null;
  created_at: string;
}

// --- Milestone 8: executive reporting ---

export interface ComplianceFrameworkSummary {
  id: string;
  key: string;
  name: string;
  score: number;
}

export interface ExecutiveSummaryRead {
  generated_at: string;
  asset_total: number;
  security_score: number;
  open_findings_total: number;
  open_findings_by_severity: Record<string, number>;
  open_incidents_total: number;
  open_incidents_by_severity: Record<string, number>;
  recovery_confidence_score: number | null;
  backup_job_total: number;
  compliance_overall_score: number | null;
  compliance_frameworks: ComplianceFrameworkSummary[];
}

// --- Milestone 9: trust passport ---

export interface TrustPassportSettingsRead {
  is_published: boolean;
  public_slug: string | null;
  headline: string;
  description: string;
  show_compliance_frameworks: boolean;
  updated_at: string | null;
}

export interface PublicFrameworkStatus {
  name: string;
  status_label: string;
}

export interface PublicTrustPassportRead {
  headline: string;
  description: string;
  generated_at: string;
  compliance_frameworks: PublicFrameworkStatus[] | null;
}

// --- Milestone 10: threat intelligence ---

export interface MatchedAssetRead {
  asset_id: string;
  asset_display_name: string;
  finding_id: string;
  finding_status: string;
}

export interface IndicatorRead {
  id: string;
  indicator_type: string;
  value: string;
  confidence: number;
  source: string;
  first_seen_at: string;
  last_seen_at: string;
  matches: MatchedAssetRead[];
}

// --- Milestone 11: attack surface ---

export interface DomainRead {
  id: string;
  domain: string;
  is_verified: boolean;
  verification_method: string | null;
  verification_token: string | null;
  verification_file_url: string;
  verified_at: string | null;
  created_at: string;
}

export interface VerifyDomainResult {
  domain: DomainRead;
  verified_now: boolean;
  message: string;
}

// --- Milestone 12: platform admin console ---

export interface PlatformTenantSummary {
  id: string;
  name: string;
  slug: string;
  status: TenantStatus;
  industry: string | null;
  country_code: string | null;
  is_demo: boolean;
  created_at: string;
}

export interface PlatformAuditLogRead {
  id: string;
  tenant_id: string | null;
  actor_user_id: string | null;
  actor_label: string;
  action: string;
  target_type: string | null;
  target_id: string | null;
  context: Record<string, unknown>;
  created_at: string;
}

// --- Milestone 13: MFA enrollment and step-up authentication ---

export interface MfaRequiredResponse {
  mfa_required: true;
  mfa_challenge_token: string;
}

export interface MfaEnrollResponse {
  secret: string;
  provisioning_uri: string;
}

export interface StepUpResponse {
  status: string;
  step_up_expires_at: string;
}

export interface TenantSecurityProfileRead {
  require_mfa_for_admins: boolean;
  require_step_up_for_disruptive_actions: boolean;
  session_ttl_seconds: number;
}
