// Mirrors of the FastAPI Pydantic schemas (apps/api/app/schemas). Kept as
// plain interfaces matching the actual snake_case JSON shape - see the
// note in packages/shared-types/src/index.ts for why.

export interface ServiceOut {
  id: string;
  category_id: string | null;
  name: string;
  slug: string;
  description: string | null;
  is_active: boolean;
  sort_order: number;
}

export interface BranchOut {
  id: string;
  name: string;
  is_active: boolean;
}

export interface TagOut {
  id: string;
  name: string;
  color: string;
}

export interface LossReasonOut {
  id: string;
  label: string;
  sort_order: number;
}

export interface PipelineStageOut {
  id: string;
  name: string;
  slug: string;
  sort_order: number;
  is_won: boolean;
  is_lost: boolean;
  is_system: boolean;
}

export interface CustomFieldOptionOut {
  value: string;
  label: string;
  sort_order: number;
}

export interface CustomFieldDefinitionOut {
  id: string;
  field_key: string;
  label: string;
  field_type: string;
  is_required: boolean;
  is_active: boolean;
  options: CustomFieldOptionOut[];
}

export interface QualificationRuleOut {
  id: string;
  depends_on_question_id: string;
  operator: string;
  depends_on_value: string;
  action: string;
}

export interface QualificationQuestionOut {
  id: string;
  sort_order: number;
  is_required: boolean;
  help_text: string | null;
  is_active: boolean;
  field_definition: CustomFieldDefinitionOut;
  rules: QualificationRuleOut[];
}

export interface QualificationFormOut {
  id: string;
  name: string;
  is_default: boolean;
  is_active: boolean;
  questions: QualificationQuestionOut[];
}

export interface LeadOut {
  id: string;
  reference_number: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  email: string | null;
  company: string | null;
  service_id: string | null;
  branch_id: string | null;
  stage_id: string;
  source: string;
  priority: string;
  score: number;
  score_reasons: unknown[];
  estimated_value: number | null;
  assigned_membership_id: string | null;
  preferred_contact_method: string | null;
  next_follow_up_at: string | null;
  consent_given: boolean;
  utm_source: string | null;
  utm_medium: string | null;
  utm_campaign: string | null;
  is_possible_duplicate: boolean;
  duplicate_of_lead_id: string | null;
  loss_reason_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface LeadAnswerOut {
  id: string;
  question_id: string | null;
  question_label_snapshot: string;
  field_type_snapshot: string;
  value: unknown;
}

export interface LeadDetailOut extends LeadOut {
  answers: LeadAnswerOut[];
  tag_ids: string[];
}

export interface LeadListOut {
  items: LeadOut[];
  total: number;
  page: number;
  page_size: number;
}

export interface LeadNoteOut {
  id: string;
  author_user_id: string | null;
  body: string;
  created_at: string;
}

export interface TimelineEntryOut {
  id: string;
  event_type: string;
  actor_user_id: string | null;
  entity_type: string | null;
  entity_id: string | null;
  event_metadata: Record<string, unknown>;
  created_at: string;
}

export interface MemberOut {
  id: string;
  user_id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: { id: string; name: string; slug: string };
  status: string;
}

export interface ScoringRuleOut {
  id: string;
  name: string;
  rule_type: string;
  config: Record<string, unknown>;
  points: number;
  sort_order: number;
  is_active: boolean;
}

export interface TenantScoringSettingsOut {
  hot_threshold: number;
  warm_threshold: number;
  standard_threshold: number;
}

export interface AssignmentRuleOut {
  id: string;
  name: string;
  strategy: string;
  config: Record<string, unknown>;
  sort_order: number;
  is_active: boolean;
  fallback_membership_id: string | null;
}

export interface TaskTypeOut {
  id: string;
  name: string;
}

export interface TaskOut {
  id: string;
  lead_id: string | null;
  task_type_id: string | null;
  title: string;
  description: string | null;
  assigned_membership_id: string | null;
  priority: string;
  status: string;
  due_at: string | null;
  completed_at: string | null;
  created_by_user_id: string | null;
  created_at: string;
  is_overdue: boolean;
}

export interface TaskListOut {
  items: TaskOut[];
  total: number;
  page: number;
  page_size: number;
}

export interface TaskCommentOut {
  id: string;
  author_user_id: string;
  body: string;
  created_at: string;
}

export interface MessageTemplateOut {
  id: string;
  key: string;
  subject: string;
  body: string;
  is_active: boolean;
}

export interface NotificationOut {
  id: string;
  title: string;
  body: string | null;
  related_entity_type: string | null;
  related_entity_id: string | null;
  is_read: boolean;
  created_at: string;
}

export interface AppointmentOut {
  id: string;
  lead_id: string;
  assigned_membership_id: string | null;
  branch_id: string | null;
  service_id: string | null;
  starts_at: string;
  ends_at: string;
  status: string;
  location_type: string;
  notes: string | null;
  cancellation_reason: string | null;
  created_by_user_id: string | null;
  created_at: string;
}

export interface AppointmentListOut {
  items: AppointmentOut[];
  total: number;
  page: number;
  page_size: number;
}

export interface TimeSlotOut {
  starts_at: string;
  ends_at: string;
}

export interface WorkflowConditionValue {
  field: string;
  operator: string;
  value: unknown;
}

export interface WorkflowActionValue {
  type: string;
  [key: string]: unknown;
}

export interface WorkflowRuleOut {
  id: string;
  name: string;
  trigger_type: string;
  conditions: WorkflowConditionValue[];
  actions: WorkflowActionValue[];
  sort_order: number;
  is_active: boolean;
}

export interface WorkflowExecutionLogOut {
  id: string;
  workflow_rule_id: string;
  lead_id: string | null;
  trigger_type: string;
  actions_taken: { type: string; result: string; error?: string }[];
  executed_at: string;
}

export const APPOINTMENT_STATUSES = [
  "scheduled",
  "confirmed",
  "completed",
  "cancelled",
  "no_show",
] as const;

export const APPOINTMENT_LOCATION_TYPES = ["in_person", "online_meeting", "phone"] as const;

export const WORKFLOW_TRIGGER_TYPES = [
  ["lead_created", "Lead created"],
  ["lead_stage_changed", "Lead stage changed"],
  ["lead_assigned", "Lead assigned"],
  ["appointment_booked", "Appointment booked"],
] as const;

export const WORKFLOW_ACTION_TYPES = [
  ["create_task", "Create a task"],
  ["send_email", "Send an email"],
  ["add_tag", "Add a tag"],
  ["create_notification", "Notify the assignee"],
] as const;

export const WORKFLOW_CONDITION_FIELDS = [
  "service_id",
  "source",
  "priority",
  "estimated_value",
  "to_stage_slug",
] as const;

export const WORKFLOW_CONDITION_OPERATORS = ["equals", "not_equals", "at_least"] as const;

export interface OverviewStatsOut {
  total_leads: number;
  hot_leads: number;
  open_tasks: number;
  overdue_tasks: number;
  upcoming_appointments: number;
}

export interface FunnelStageOut {
  stage_id: string;
  name: string;
  sort_order: number;
  is_won: boolean;
  is_lost: boolean;
  lead_count: number;
}

export interface SourceCountOut {
  source: string;
  count: number;
}

export interface PriorityCountOut {
  priority: string;
  count: number;
}

export interface MemberPerformanceOut {
  membership_id: string;
  member_name: string;
  leads_assigned: number;
  leads_won: number;
}

export interface TaskStatsOut {
  open: number;
  overdue: number;
  completed_last_30_days: number;
}

export interface AppointmentStatsOut {
  scheduled: number;
  confirmed: number;
  completed: number;
  cancelled: number;
  no_show: number;
}

export interface DashboardReportOut {
  overview: OverviewStatsOut;
  pipeline_funnel: FunnelStageOut[];
  lead_sources: SourceCountOut[];
  score_distribution: PriorityCountOut[];
  team_performance: MemberPerformanceOut[];
  task_stats: TaskStatsOut;
  appointment_stats: AppointmentStatsOut;
}

export const SCORING_RULE_TYPES = [
  ["service_equals", "Service equals"],
  ["source_equals", "Source equals"],
  ["estimated_value_at_least", "Estimated value at least"],
  ["consent_given", "Consent given"],
  ["complete_contact_info", "Complete contact info"],
  ["repeat_enquiry", "Repeat enquiry"],
  ["answer_equals", "Qualification answer equals"],
] as const;

export const ASSIGNMENT_STRATEGIES = [
  ["round_robin", "Round robin"],
  ["service_based", "Service based"],
  ["branch_based", "Branch based"],
  ["priority_based", "Priority based"],
  ["manual_fallback", "Manual fallback"],
] as const;

export const TASK_PRIORITIES = ["low", "normal", "high"] as const;

export const PRIORITY_LABELS: Record<string, string> = {
  hot: "Hot",
  warm: "Warm",
  standard: "Standard",
  low_priority: "Low Priority",
};

export const PRIORITY_TONES: Record<string, "danger" | "warning" | "neutral" | "accent"> = {
  hot: "danger",
  warm: "warning",
  standard: "neutral",
  low_priority: "neutral",
};
