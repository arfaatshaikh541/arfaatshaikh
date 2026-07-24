-- Milestone 11: three genuinely new permission keys. Everything else this
-- milestone needs was already seeded in migration 0002 (Milestone 1) in
-- anticipation of exactly this milestone -- the richest "roles anticipate
-- milestones" case yet: usage.view/billing.view (enterprise) and
-- operator.pricing.manage/operator.usage.view/operator.settlements.view
-- (operator) already exist, already granted to finops_manager/
-- application_owner and operator_finance_manager/operator_product_manager/
-- operator_auditor respectively, and are activated for real enforcement
-- here for the first time.
--
-- budgets.manage (enterprise) gates defining/archiving a tenant's own
-- spend budgets -- narrower than usage.view/billing.view (viewing usage
-- and invoices is broad, setting a spend cap is not), mirroring
-- Milestone 10's slos.manage/assurance.view split exactly.
--
-- billing.dispute (enterprise) gates opening a dispute against an invoice
-- -- a distinct, narrower action from merely viewing billing.view
-- (reading invoices, disputes, credit notes).
--
-- operator.settlements.manage (operator) gates creating/reconciling
-- settlement records and issuing adjustments/credit notes -- narrower than
-- the already-seeded operator.settlements.view (viewing is broad, settling
-- revenue and issuing corrections is not).
INSERT INTO permissions (key, scope_type, description) VALUES
    ('budgets.manage', 'enterprise', 'Define and archive spend budgets for the tenant''s own usage'),
    ('billing.dispute', 'enterprise', 'Open a dispute against an issued invoice'),
    ('operator.settlements.manage', 'operator', 'Create and reconcile settlement records, issue adjustments and credit notes')
ON CONFLICT DO NOTHING;

-- Enterprise Owner and Enterprise Administrator already receive every
-- enterprise permission via migration 0002's blanket grant, which does not
-- retroactively pick up permissions inserted later -- granted explicitly
-- here, same as every prior milestone's permissions migration.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'enterprise' AND r.key IN ('enterprise_owner', 'enterprise_admin')
  AND p.key IN ('budgets.manage', 'billing.dispute')
ON CONFLICT DO NOTHING;

-- budgets.manage goes to the same roles finops_manager already shares
-- billing.view/usage.view with, plus ai_platform_engineer/devops_engineer
-- (who already hold Milestone 10's slos.manage for the identical
-- "reliability/spend configuration" reasoning).
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'enterprise'
  AND r.key IN ('finops_manager', 'ai_platform_engineer', 'devops_engineer')
  AND p.key = 'budgets.manage'
ON CONFLICT DO NOTHING;

-- billing.dispute goes to finops_manager (the role already holding
-- billing.view) and compliance_manager (whose existing approvals.respond
-- role already makes it a dispute-handling participant elsewhere).
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'enterprise'
  AND r.key IN ('finops_manager', 'compliance_manager')
  AND p.key = 'billing.dispute'
ON CONFLICT DO NOTHING;

-- Operator Platform Owner already receives every operator permission via
-- migration 0002's blanket grant, same caveat as above.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'operator' AND r.key = 'operator_platform_owner'
  AND p.key = 'operator.settlements.manage'
ON CONFLICT DO NOTHING;

-- Operator Finance Manager is the role this permission was clearly seeded
-- in anticipation of -- it already holds operator.pricing.manage and
-- operator.settlements.view, the two closest-adjacent permissions to
-- "manage settlements" that exist.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'operator' AND r.key = 'operator_finance_manager'
  AND p.key = 'operator.settlements.manage'
ON CONFLICT DO NOTHING;
