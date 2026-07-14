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

export interface PublicService {
  id: string;
  name: string;
  description: string;
}

export type QuestionType =
  | "short_text"
  | "long_text"
  | "email"
  | "phone"
  | "number"
  | "currency"
  | "date"
  | "single_select"
  | "multi_select"
  | "checkbox"
  | "yes_no";

export interface QuestionOption {
  id: string;
  label: string;
  value: string;
}

export interface QualificationQuestion {
  id: string;
  label: string;
  question_type: QuestionType;
  is_required: boolean;
  sort_order: number;
  maps_to_field?: string | null;
  options: QuestionOption[];
}

export interface PipelineStage {
  id: string;
  name: string;
  sort_order: number;
  is_won: boolean;
  is_lost: boolean;
}

export interface Pipeline {
  id: string;
  name: string;
  is_default: boolean;
  stages: PipelineStage[];
}

export interface LeadSummary {
  id: string;
  reference_number: string;
  first_name: string;
  last_name: string;
  email: string | null;
  phone: string | null;
  company: string | null;
  service_id: string | null;
  stage_id: string | null;
  priority: "low" | "medium" | "high";
  assigned_user_id: string | null;
  is_possible_duplicate: boolean;
  created_at: string;
}

export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface LeadDetail {
  id: string;
  reference_number: string;
  first_name: string;
  last_name: string;
  email: string | null;
  phone: string | null;
  company: string | null;
  service_id: string | null;
  stage_id: string | null;
  pipeline_id: string | null;
  priority: "low" | "medium" | "high";
  estimated_value: number | null;
  assigned_user_id: string | null;
  preferred_contact_method: string | null;
  consent_status: string;
  is_possible_duplicate: boolean;
  duplicate_of_lead_id: string | null;
  created_at: string;
}

export interface ActivityItem {
  id: string;
  actor_id: string | null;
  activity_type: string;
  summary: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface NoteItem {
  id: string;
  author_id: string | null;
  body: string;
  created_at: string;
}

export interface TagItem {
  id: string;
  name: string;
  color: string;
}

export interface TaskItem {
  id: string;
  lead_id: string | null;
  title: string;
  description: string;
  assigned_user_id: string | null;
  due_at: string | null;
  priority: "low" | "medium" | "high";
  status: "open" | "completed";
  completed_at: string | null;
  source: string;
  created_at: string;
}

export interface AttachmentItem {
  id: string;
  file_name: string;
  content_type: string;
  size_bytes: number;
  uploaded_by: string | null;
  created_at: string;
}
