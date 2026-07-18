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

export type Business = {
  id: string;
  name: string;
  category: string | null;
  subcategory: string | null;
  address: string | null;
  country: string | null;
  region: string | null;
  city: string | null;
  area: string | null;
  latitude: number | null;
  longitude: number | null;
  phone: string | null;
  email: string | null;
  website: string | null;
  canonical_domain: string | null;
  google_place_id: string | null;
  google_maps_url: string | null;
  rating: number | null;
  review_count: number | null;
  business_status: string | null;
  field_provenance: Record<string, unknown>;
  merged_into_id: string | null;
  created_at: string;
};

export type Member = {
  user_id: string;
  email: string;
  full_name: string;
  role_id: string;
  role_name: string;
};

export const LEAD_STATUSES = [
  "new",
  "reviewed",
  "qualified",
  "unqualified",
  "assigned",
  "contacted",
  "interested",
  "converted",
  "do_not_contact",
  "archived",
] as const;

export type LeadStatus = (typeof LEAD_STATUSES)[number];

export type Lead = {
  id: string;
  business_id: string;
  status: LeadStatus;
  assigned_to_user_id: string | null;
  created_at: string;
};

export type ScoreFactor = {
  key: string;
  label: string;
  score: number;
  max_score: number;
  explanation: string;
  evidence: Record<string, unknown>;
};

export type LeadScore = {
  id: string;
  algorithm_version: string;
  total_score: number;
  max_score: number;
  factors: ScoreFactor[];
  calculated_at: string;
};

export type LeadOpportunity = {
  id: string;
  opportunity_type: string;
  confidence: number;
  evidence_reference: Record<string, unknown>;
  detected_at: string;
};

export type LeadRecommendation = {
  id: string;
  recommendation_type: string;
  confidence: number;
  supporting_opportunity_ids: string[];
  recommended_at: string;
};

export type NoteEntry = {
  id: string;
  author_user_id: string | null;
  body: string;
  created_at: string;
};

export type StatusHistoryEntry = {
  id: string;
  from_status: string;
  to_status: string;
  changed_by_user_id: string | null;
  changed_at: string;
  note: string | null;
};

export type AssignmentEntry = {
  id: string;
  assigned_to_user_id: string;
  assigned_by_user_id: string | null;
  assigned_at: string;
  unassigned_at: string | null;
};

export type DuplicateCandidate = {
  id: string;
  business_id_a: string;
  business_id_b: string;
  match_type: string;
  confidence: number;
  matched_fields: Record<string, unknown>;
  status: string;
  reviewed_at: string | null;
};

export type LeadListItem = {
  lead_id: string;
  business_id: string;
  business_name: string;
  category: string | null;
  city: string | null;
  country: string | null;
  area: string | null;
  phone: string | null;
  email: string | null;
  website: string | null;
  rating: number | null;
  review_count: number | null;
  business_status: string | null;
  status: LeadStatus;
  assigned_to_user_id: string | null;
  score: number | null;
  tags: string[];
  created_at: string;
};

export type LeadListResponse = {
  items: LeadListItem[];
  total: number;
  page: number;
  page_size: number;
};

export type LeadDetail = {
  lead: Lead;
  business_id: string;
  latest_score: LeadScore | null;
  opportunities: LeadOpportunity[];
  recommendations: LeadRecommendation[];
  notes: NoteEntry[];
  tags: string[];
  status_history: StatusHistoryEntry[];
  assignment_history: AssignmentEntry[];
  duplicate_candidates: DuplicateCandidate[];
};

export type SavedView = {
  id: string;
  name: string;
  created_by_user_id: string | null;
  filters: Record<string, unknown>;
  created_at: string;
};

export type LeadListFilterState = {
  status?: string[];
  assigned_to_user_id?: string;
  unassigned_only?: boolean;
  tag?: string;
  category?: string;
  city?: string;
  country?: string;
  area?: string;
  min_score?: number;
  max_score?: number;
  search?: string;
  sort_by?: string;
  sort_dir?: string;
};

export type ExportFormat = "xlsx" | "csv";
export type ExportStatus = "pending" | "processing" | "completed" | "failed";

export type ExportRecord = {
  id: string;
  format: ExportFormat;
  status: ExportStatus;
  row_count: number | null;
  error_count: number;
  file_size_bytes: number | null;
  requested_by_user_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  created_at: string;
};

export type ExportListResponse = {
  exports: ExportRecord[];
};

export type ExportDownload = {
  url: string;
  expires_in_seconds: number;
  filename: string;
};
