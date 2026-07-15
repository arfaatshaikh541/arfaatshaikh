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
  priority_locked: boolean;
  score: number | null;
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

export type ScoringOperator = "equals" | "not_equals" | "contains" | "greater_than" | "less_than" | "is_set" | "in";

export interface ScoringRule {
  id: string;
  name: string;
  field: string;
  operator: ScoringOperator;
  value: unknown;
  points: number;
  sort_order: number;
  is_active: boolean;
}

export interface ScoringSettings {
  hot_threshold: number;
  warm_threshold: number;
  auto_priority: boolean;
}

export interface ScoreBreakdownEntry {
  rule_id: string;
  rule_name: string;
  points: number;
}

export interface ScoreBreakdown {
  total_score: number | null;
  breakdown: ScoreBreakdownEntry[];
  computed_at: string | null;
}

export type AssignmentStrategy = "round_robin" | "service_based" | "priority_based";

export interface AssignmentRule {
  id: string;
  name: string;
  strategy: AssignmentStrategy;
  conditions: Record<string, unknown>;
  eligible_user_ids: string[];
  sort_order: number;
  is_active: boolean;
}

export type EmailTriggerEvent = "manual" | "lead_created" | "lead_assigned" | "stage_changed" | "task_reminder";

export interface EmailTemplate {
  id: string;
  name: string;
  trigger_event: EmailTriggerEvent;
  trigger_stage_outcome: string | null;
  subject: string;
  body_text: string;
  body_html: string | null;
  is_active: boolean;
}

export interface EmailDeliveryLog {
  id: string;
  template_id: string | null;
  lead_id: string | null;
  recipient: string;
  subject: string;
  status: "pending" | "sent" | "failed";
  attempt_count: number;
  last_error: string | null;
  sent_at: string | null;
  created_at: string;
}

export interface TenantMember {
  membership_id: string;
  user_id: string;
  email: string;
  first_name: string;
  last_name: string;
  role_name: string;
  status: string;
}

export interface AppointmentTypeItem {
  id: string;
  name: string;
  description: string;
  duration_minutes: number;
  is_active: boolean;
}

export interface AvailabilityWindow {
  id?: string;
  day_of_week: number;
  start_time: string;
  end_time: string;
}

export interface AvailabilityExceptionItem {
  id: string;
  date: string;
  reason: string;
}

export type AppointmentStatus = "scheduled" | "completed" | "cancelled" | "no_show";

export interface AppointmentItem {
  id: string;
  lead_id: string | null;
  staff_user_id: string;
  appointment_type_id: string | null;
  title: string;
  starts_at: string;
  ends_at: string;
  status: AppointmentStatus;
  location: string;
  notes: string;
  cancelled_reason: string | null;
  created_by: string | null;
}

export interface AvailableSlot {
  start: string;
  end: string;
}

export type WorkflowTriggerEvent =
  | "lead_created"
  | "stage_changed"
  | "score_threshold_reached"
  | "tag_added"
  | "appointment_booked"
  | "appointment_completed";

export type WorkflowActionType = "send_email_template" | "create_task" | "change_stage" | "add_tag";

export type WorkflowConditionOperator = "equals" | "not_equals" | "contains" | "greater_than" | "less_than" | "is_set" | "in";

export interface WorkflowCondition {
  field: string;
  operator: WorkflowConditionOperator;
  value: unknown;
}

export interface WorkflowItem {
  id: string;
  name: string;
  description: string;
  trigger_event: WorkflowTriggerEvent;
  trigger_config: Record<string, unknown>;
  conditions: WorkflowCondition[];
  is_active: boolean;
  sort_order: number;
}

export interface WorkflowStepItem {
  id: string;
  sequence_order: number;
  delay_minutes: number;
  action_type: WorkflowActionType;
  action_config: Record<string, unknown>;
}

export type WorkflowRunStatus = "running" | "completed" | "cancelled" | "failed";

export interface WorkflowRunItem {
  id: string;
  workflow_id: string;
  lead_id: string;
  status: WorkflowRunStatus;
  current_step_index: number;
  next_run_at: string | null;
  triggered_at: string;
}

export interface WorkflowStepLogItem {
  id: string;
  step_id: string;
  status: "executed" | "failed" | "skipped";
  result_summary: string;
  executed_at: string;
}

export interface LineItem {
  id: string;
  description: string;
  quantity: number;
  unit_price: number;
  sort_order: number;
}

export interface LineItemInput {
  description: string;
  quantity: number;
  unit_price: number;
}

export interface ProposalTemplate {
  id: string;
  name: string;
  description: string;
  terms: string;
  is_active: boolean;
  line_items: LineItem[];
}

export type ProposalStatus = "draft" | "sent" | "viewed" | "accepted" | "rejected" | "expired";

export interface ProposalItem {
  id: string;
  lead_id: string;
  template_id: string | null;
  title: string;
  status: ProposalStatus;
  currency: string;
  tax_rate: number;
  terms: string;
  valid_until: string | null;
  public_token: string | null;
  sent_at: string | null;
  viewed_at: string | null;
  accepted_at: string | null;
  accepted_by_name: string | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  line_items: LineItem[];
  subtotal: number;
  tax_amount: number;
  total: number;
}

export interface PublicProposal {
  title: string;
  status: ProposalStatus;
  currency: string;
  tax_rate: number;
  terms: string;
  valid_until: string | null;
  tenant_name: string;
  line_items: { description: string; quantity: number; unit_price: number }[];
  subtotal: number;
  tax_amount: number;
  total: number;
}

export type DocumentRequestStatus = "requested" | "uploaded" | "approved" | "rejected";

export interface DocumentRequestItem {
  id: string;
  lead_id: string;
  title: string;
  description: string;
  status: DocumentRequestStatus;
  public_token: string | null;
  review_notes: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
}

export interface DocumentItem {
  id: string;
  file_name: string;
  content_type: string;
  size_bytes: number;
  uploaded_by: string | null;
  created_at: string;
}

export interface PublicDocumentRequest {
  title: string;
  description: string;
  status: DocumentRequestStatus;
}

export type OnboardingStepType = "task" | "document_request";
export type OnboardingCaseStatus = "not_started" | "in_progress" | "completed" | "cancelled";
export type OnboardingCaseStepStatus = "pending" | "completed" | "skipped";

export interface OnboardingTemplateStepItem {
  id: string;
  step_type: OnboardingStepType;
  title: string;
  description: string;
  due_in_days: number | null;
  sort_order: number;
}

export interface OnboardingTemplateItem {
  id: string;
  name: string;
  description: string;
  is_active: boolean;
  steps: OnboardingTemplateStepItem[];
}

export interface OnboardingCaseStepInstance {
  id: string;
  step_type: OnboardingStepType;
  title: string;
  description: string;
  status: OnboardingCaseStepStatus;
  task_id: string | null;
  document_request_id: string | null;
  completed_at: string | null;
  sort_order: number;
}

export interface OnboardingCaseItem {
  id: string;
  lead_id: string;
  template_id: string | null;
  name: string;
  status: OnboardingCaseStatus;
  started_at: string | null;
  completed_at: string | null;
  steps: OnboardingCaseStepInstance[];
}

export type DeadlineStatus = "open" | "completed";

export interface DeadlineItem {
  id: string;
  lead_id: string;
  title: string;
  description: string;
  due_date: string;
  status: DeadlineStatus;
  recurrence_interval_days: number | null;
  completed_at: string | null;
}

export interface PortalAccountItem {
  id: string;
  lead_id: string;
  email: string;
  is_active: boolean;
  created_at: string;
}

export interface CurrentPortalAccount {
  id: string;
  tenant_id: string;
  tenant_name: string;
  lead_id: string;
  email: string;
  first_name: string;
  last_name: string;
}

export interface PortalProposal {
  id: string;
  title: string;
  status: ProposalStatus;
  currency: string;
  terms: string;
  valid_until: string | null;
  line_items: { description: string; quantity: number; unit_price: number }[];
  subtotal: number;
  tax_amount: number;
  total: number;
}

export interface PortalDocumentRequest {
  id: string;
  title: string;
  description: string;
  status: DocumentRequestStatus;
  review_notes: string;
}

export interface PortalOnboardingCase {
  id: string;
  name: string;
  status: OnboardingCaseStatus;
  steps: { title: string; step_type: OnboardingStepType; status: OnboardingCaseStepStatus }[];
}

export interface PortalAppointment {
  id: string;
  title: string;
  starts_at: string;
  ends_at: string;
  status: AppointmentStatus;
  location: string;
}

export interface PortalDeadline {
  id: string;
  title: string;
  description: string;
  due_date: string;
  status: DeadlineStatus;
}
