-- Milestone 9: one new permission key on each side.
--
-- network.view (enterprise) gates browsing the network-service marketplace
-- and viewing a tenant's own requests/evaluations/reservations -- mirrors
-- capacity.view's role exactly (see below), since network services are the
-- same kind of infrastructure-marketplace concern Milestone 5 already
-- established a permission-granting pattern for. reservations.create/
-- reservations.cancel (seeded in migration 0002) are deliberately *reused*
-- for network reservation lifecycle actions rather than duplicated as
-- network.request/network.cancel -- both keys are already generically
-- named ("reservations.*", not "capacity_reservations.*"), and the same
-- infra/platform-engineering roles that hold them for capacity reservations
-- are the right roles to hold them for network reservations too. See
-- docs/project-status.md's Deliberate security decisions for Milestone 9.
--
-- operator.network.manage (operator) gates publishing/pausing/withdrawing
-- network service offers -- the permission the pre-existing
-- operator_network_administrator role (seeded in migration 0002, described
-- as "Manages operator network capabilities") was clearly anticipating: it
-- held no network-specific permission at all until now, only
-- operator.deployments.view/operator.regions.manage. Viewing reservations
-- held against an operator's own offers reuses operator.reservations.view
-- (seeded in migration 0025), the same generic-view-permission reasoning.
INSERT INTO permissions (key, scope_type, description) VALUES
    ('network.view', 'enterprise', 'View network service offers and the tenant''s own requests/reservations'),
    ('operator.network.manage', 'operator', 'Publish and manage network service offers for operator infrastructure')
ON CONFLICT DO NOTHING;

-- Enterprise Owner and Enterprise Administrator already receive every
-- enterprise permission via migration 0002's blanket grant, which does not
-- retroactively pick up permissions inserted later -- granted explicitly
-- here, same as every prior milestone's permissions migration.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'enterprise' AND r.key IN ('enterprise_owner', 'enterprise_admin')
  AND p.key = 'network.view'
ON CONFLICT DO NOTHING;

-- network.view is granted to exactly the roles that already hold
-- capacity.view -- the same "views the infrastructure marketplace" concern.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'enterprise'
  AND r.key IN ('ai_platform_engineer', 'devops_engineer', 'finops_manager', 'read_only_auditor')
  AND p.key = 'network.view'
ON CONFLICT DO NOTHING;

-- Operator Platform Owner already receives every operator permission via
-- migration 0002's blanket grant, same caveat as above.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'operator' AND r.key = 'operator_platform_owner'
  AND p.key = 'operator.network.manage'
ON CONFLICT DO NOTHING;

-- Operator Network Administrator is the role this permission was clearly
-- seeded in anticipation of -- see this migration's header comment.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'operator' AND r.key = 'operator_network_administrator'
  AND p.key = 'operator.network.manage'
ON CONFLICT DO NOTHING;
