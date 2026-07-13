# Entity Relationship Summary — Milestone 2 Addendum

Adds services & custom fields (Module 3), lead capture (Module 4), CRM
pipeline (Module 5), and activity timeline (Module 6, reusing the
`audit_logs` table from Milestone 1) on top of the Milestone 1 foundation.
All tables below carry `tenant_id` and follow the same isolation pattern
established in `erd-summary.md`.

```
service_categories
  id, tenant_id, name, sort_order

services
  id, tenant_id, category_id (nullable FK), name, slug, description,
  is_active, sort_order
  UNIQUE(tenant_id, slug)

branches
  id, tenant_id, name, is_active

pipeline_stages
  id, tenant_id, name, slug, sort_order, is_won, is_lost, is_system
  UNIQUE(tenant_id, slug)

tags
  id, tenant_id, name, color
  UNIQUE(tenant_id, name)

loss_reasons
  id, tenant_id, label, sort_order

custom_field_definitions
  id, tenant_id, entity_type ('lead'), field_key, label, field_type
  (short_text|long_text|email|phone|number|currency|date|single_select|
  multi_select|checkbox|yes_no), is_required, sort_order, is_active
  UNIQUE(tenant_id, entity_type, field_key)

custom_field_options
  id, field_definition_id, value, label, sort_order

qualification_forms
  id, tenant_id, name, is_default, is_active

qualification_questions
  id, form_id, field_definition_id (FK -> custom_field_definitions),
  sort_order, is_required, help_text, is_active

qualification_rules                          -- conditional visibility
  id, question_id, depends_on_question_id, operator ('equals'),
  depends_on_value, action ('show')

leads
  id, tenant_id, reference_number (UNIQUE per tenant), first_name,
  last_name, phone, email, company, service_id (nullable FK),
  branch_id (nullable FK), stage_id (FK -> pipeline_stages),
  source (public_form|widget|manual|api|webhook|csv_import|whatsapp),
  priority (hot|warm|standard|low_priority), score, score_reasons (jsonb -
  genuinely free-form explanation list, see scoring engine in M3),
  estimated_value, assigned_membership_id (nullable FK -> memberships),
  preferred_contact_method (phone|whatsapp|email|online_meeting),
  next_follow_up_at, consent_given, consent_text_shown, consented_at,
  utm_source, utm_medium, utm_campaign, utm_term, utm_content,
  referrer_url, loss_reason_id (nullable FK), is_possible_duplicate,
  duplicate_of_lead_id (nullable FK -> leads), created_at, updated_at

lead_answers                                  -- immutable-ish snapshot
  id, lead_id, question_id (nullable FK, SET NULL if question hard-deleted),
  question_label_snapshot, field_type_snapshot, value (jsonb - answer
  shape depends on field_type, genuinely variable), created_at

lead_tags
  lead_id, tag_id  (PK)

lead_stage_history
  id, lead_id, from_stage_id, to_stage_id, changed_by_user_id, reason,
  created_at

lead_notes
  id, lead_id, author_user_id, body, created_at

idempotency_keys                              -- public submission dedup
  id, tenant_id, key, request_hash, lead_id, created_at
  UNIQUE(tenant_id, key)

public_form_attempts                          -- rate limiting, append-only
  id, tenant_id, ip_address, created_at
```

## Activity Timeline (Module 6)

Reuses `audit_logs` from Milestone 1 rather than a new table — it already
has `tenant_id`, `actor_user_id`, `entity_type`, `entity_id`, `event_type`,
`metadata`, `correlation_id`, `created_at`, which is exactly the timeline
shape required. `LeadService` writes an audit entry for every lead
lifecycle event (`lead.created`, `lead.updated`, `lead.stage_changed`,
`lead.assigned`, `lead.note_added`, `lead.tag_added`) and the timeline
endpoint is `GET /tenants/me/leads/{id}/timeline`, which is
`AuditLogRepository.list_for_tenant` filtered by `entity_type='lead'` and
`entity_id`.

## Public Enquiry Identifier

`tenants.public_key` (UUID, unique, indexed) is added to the `tenants`
table: a dedicated, non-guessable identifier used only by public,
unauthenticated enquiry-form endpoints, distinct from the tenant's
internal `id` (used by authenticated API calls) and `slug` (human-facing,
used in the tenant app URL). This keeps the identifier that's embedded in
public-facing HTML/JS separate from identifiers used in authenticated
contexts.

## Explicitly Deferred From Milestone 2

- File attachments (S3-compatible upload/signed URLs) - a cross-cutting
  storage subsystem better delivered as a complete unit rather than a
  partial upload endpoint; tracked as a follow-up.
- Saved views, CSV import, WhatsApp adapter - later milestones per the
  product delivery phases.
- Full assignment engine (round-robin/workload rules) - Milestone 3.
  Milestone 2 supports only direct manual assignment of a lead to a
  tenant member.
