-- Milestone 5: two new permission keys. Every other permission
-- placement/capacity work needs (reservations.create, reservations.cancel,
-- capacity.view, regions.view, regions.select on the enterprise side;
-- operator.capacity.manage on the operator side) was already seeded in
-- migration 0002 in anticipation of this milestone and is already granted
-- to the relevant roles -- confirmed by inspection, not re-inserted here.
--
-- reservations.approve gates the dual-control commit step: a capacity
-- reservation held against a workload version with
-- deployment_approval_required=true cannot become 'committed' until a
-- different user holding this permission approves it (mirrors
-- models.approve/images.approve/vulnerability_exceptions.approve exactly).
--
-- operator.reservations.view lets operator staff see reservations held
-- against their own capacity_offers -- capacity_reservations' dual-scope
-- RLS already makes those rows visible at the database level, but a
-- distinct permission still gates the API/UI the same way every other
-- operator resource requires its own permission to view.
INSERT INTO permissions (key, scope_type, description) VALUES
    ('reservations.approve', 'enterprise', 'Approve a capacity reservation commit (dual control)'),
    ('operator.reservations.view', 'operator', 'View reservations held against operator capacity')
ON CONFLICT DO NOTHING;

-- Enterprise Owner and Enterprise Administrator already receive every
-- enterprise permission via migration 0002's blanket grant, which does not
-- retroactively pick up permissions inserted later -- granted explicitly
-- here, same as every prior milestone's permissions migration.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'enterprise' AND r.key IN ('enterprise_owner', 'enterprise_admin')
  AND p.key = 'reservations.approve'
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'enterprise' AND r.key = 'security_administrator'
  AND p.key = 'reservations.approve'
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'enterprise' AND r.key = 'compliance_manager'
  AND p.key = 'reservations.approve'
ON CONFLICT DO NOTHING;

-- Operator Platform Owner already receives every operator permission via
-- migration 0002's blanket grant, same caveat as above.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'operator' AND r.key = 'operator_platform_owner'
  AND p.key = 'operator.reservations.view'
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'operator' AND r.key = 'operator_capacity_manager'
  AND p.key = 'operator.reservations.view'
ON CONFLICT DO NOTHING;
