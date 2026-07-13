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
