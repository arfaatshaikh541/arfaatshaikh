# Entity Relationship Summary — Milestone 3 Addendum

Adds lead scoring (Module 7), the assignment engine (Module 8), tasks &
follow-ups (Module 9), and the first slice of the communications layer
(Module 10: templates, in-app notifications, email wiring) on top of
Milestones 1-2. All tables carry `tenant_id` and follow the established
isolation pattern.

```
scoring_rules
  id, tenant_id, name, rule_type, config (jsonb - shape depends on
  rule_type, e.g. {"service_id": "..."} or {"min_value": 5000}),
  points, sort_order, is_active

tenant_scoring_settings
  id, tenant_id (unique), hot_threshold, warm_threshold, standard_threshold
  -- score >= hot_threshold -> "hot"; >= warm_threshold -> "warm";
  -- >= standard_threshold -> "standard"; else "low_priority"

assignment_rules
  id, tenant_id, name, strategy (round_robin|service_based|branch_based|
  priority_based|manual_fallback), config (jsonb - e.g.
  {"service_id": "...", "membership_ids": [...]}), sort_order, is_active,
  fallback_membership_id (nullable)

assignment_rule_state                        -- round-robin cursor
  id, rule_id (unique), last_assigned_index

task_types
  id, tenant_id, name

tasks
  id, tenant_id, lead_id (nullable FK), task_type_id (nullable FK),
  title, description, assigned_membership_id (nullable), priority,
  status (open|completed), due_at, completed_at, created_by_user_id,
  created_at, updated_at

task_comments
  id, task_id, author_user_id, body, created_at

message_templates
  id, tenant_id, key (acknowledgement|assignment_alert|
  appointment_confirmation|appointment_reminder|follow_up|invitation|
  password_reset), subject, body (contains {{variable}} placeholders -
  rendered by safe string substitution only, never eval), is_active
  UNIQUE(tenant_id, key)

message_logs                                  -- append-only delivery record
  id, tenant_id, template_key, channel (email|internal_notification),
  recipient, lead_id (nullable), status (sent|failed), error_message,
  created_at

notifications                                 -- in-app notification channel
  id, tenant_id, user_id, title, body, related_entity_type,
  related_entity_id, is_read, created_at
```

## Design Notes

- **Scoring is rule-based and explainable, not ML-based**, per the
  product requirement. `ScoringService.compute` returns both a total
  score and a list of `{rule_name, points}` reasons, persisted on
  `leads.score_reasons` (already a jsonb column from Milestone 2) so the
  UI can show exactly why a lead scored the way it did.
- **Score recalculation** happens synchronously inside `LeadService` right
  after create/update of any scoring-relevant field (service, estimated
  value, consent, answers) - not via a background job - so the score
  shown is never stale relative to what's in the database.
- **Assignment rules are evaluated in `sort_order`**, first match wins;
  `manual_fallback` (the tenant's configured fallback member) is used
  when no rule matches or the matched rule's targets have no available
  member. Every assignment - rule-based or manual - is recorded via the
  same `lead.assigned` audit event added in Milestone 1/2, now carrying
  `{"strategy": ..., "rule_id": ...}` in its metadata when automatic.
- **Message templates use `{variable}` substitution via Python's
  `str.format_map` with a `defaultdict`-style safe mapping** - unknown
  variables render as empty rather than raising, and there is no
  `eval`/`exec` anywhere in the rendering path, per the explicit
  "no unsafe arbitrary-code" requirement.
- **Notifications are a real, queryable in-app channel** (not just
  emails): `GET /tenants/me/notifications` + unread count, so later
  milestones (workflow engine) have a channel to write into without
  redesigning storage.
