-- Milestone 10: two new permission keys, plus the first-ever grant of an
-- already-seeded-but-unenforced-until-now one.
--
-- assurance.view (enterprise) gates the correlated health/incident/SLO/
-- alert dashboard for a tenant's own workloads/deployments -- mirrors
-- capacity.view/network.view's role exactly, since this is the same kind of
-- "view the platform's own signal" concern those permissions already
-- established a granting pattern for.
--
-- slos.manage (enterprise) gates defining/archiving a tenant's own SLO
-- targets -- narrower than assurance.view (viewing is broad, setting
-- targets is not), granted only to the roles that actually operate
-- workloads day to day.
--
-- incidents.view/incidents.manage/operator.incidents.manage (all seeded in
-- migration 0002, Milestone 1) are deliberately NOT re-granted here beyond
-- what Milestone 1 already assigned -- this milestone activates real
-- enforcement for them, it does not change who holds them. See
-- docs/project-status.md's Deliberate security decisions for Milestone 10.
--
-- operator.sla.manage (seeded in migration 0002, Milestone 1, described as
-- "Manage operator SLAs" but never once granted to any role until now) is
-- the clearest "roles anticipate milestones" case this project has found
-- yet: a permission that existed with zero grants for nine milestones,
-- waiting for exactly this one.
INSERT INTO permissions (key, scope_type, description) VALUES
    ('assurance.view', 'enterprise', 'View correlated health, incidents, SLOs, and alerts for the tenant''s own workloads'),
    ('slos.manage', 'enterprise', 'Define and archive SLO targets for the tenant''s own workloads')
ON CONFLICT DO NOTHING;

-- Enterprise Owner and Enterprise Administrator already receive every
-- enterprise permission via migration 0002's blanket grant, which does not
-- retroactively pick up permissions inserted later -- granted explicitly
-- here, same as every prior milestone's permissions migration.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'enterprise' AND r.key IN ('enterprise_owner', 'enterprise_admin')
  AND p.key IN ('assurance.view', 'slos.manage')
ON CONFLICT DO NOTHING;

-- assurance.view is granted to exactly the roles that already hold
-- capacity.view/network.view -- the same "views the platform's own signal"
-- concern.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'enterprise'
  AND r.key IN ('ai_platform_engineer', 'devops_engineer', 'finops_manager', 'read_only_auditor')
  AND p.key = 'assurance.view'
ON CONFLICT DO NOTHING;

-- slos.manage goes only to the roles that operate workloads day to day,
-- not to finops_manager (billing-focused) or read_only_auditor (view-only
-- by definition).
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'enterprise'
  AND r.key IN ('ai_platform_engineer', 'devops_engineer')
  AND p.key = 'slos.manage'
ON CONFLICT DO NOTHING;

-- Operator Platform Owner already receives every operator permission via
-- migration 0002's blanket grant, same caveat as above.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'operator' AND r.key = 'operator_platform_owner'
  AND p.key = 'operator.sla.manage'
ON CONFLICT DO NOTHING;

-- Operator Infrastructure Administrator is the role whose existing remit
-- (capacity/clusters/locations) an SLA commitment on that same
-- infrastructure most naturally belongs to.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'operator' AND r.key = 'operator_infrastructure_administrator'
  AND p.key = 'operator.sla.manage'
ON CONFLICT DO NOTHING;
