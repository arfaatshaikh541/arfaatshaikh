-- Milestone 4: Workload and Model Registry -- new permission keys.
--
-- Enterprise Owner/Administrator's "every enterprise permission" grant and
-- Read-Only Auditor's "every *.view permission" grant (both from migration
-- 0002) are re-run here with their exact original WHERE clauses rather than
-- re-listing every key by hand -- since those clauses match against
-- `permissions` at the time they run, re-running them after inserting the
-- new keys below picks up exactly the new permissions that clause was
-- always meant to cover, and ON CONFLICT DO NOTHING makes the re-run safe
-- against rows already granted.

INSERT INTO permissions (key, scope_type, description) VALUES
    ('workloads.publish', 'enterprise', 'Publish a workload version (becomes immutable)'),
    ('workloads.retire', 'enterprise', 'Retire a workload or workload version'),
    ('models.edit', 'enterprise', 'Edit a draft model version'),
    ('models.approve', 'enterprise', 'Approve a model version for use (dual control)'),
    ('artefacts.view', 'enterprise', 'View artefact metadata'),
    ('artefacts.delete', 'enterprise', 'Delete/retire an uploaded artefact'),
    ('images.view', 'enterprise', 'View registered container images'),
    ('images.register', 'enterprise', 'Register a container image by digest'),
    ('images.approve', 'enterprise', 'Approve a container image for use'),
    ('images.revoke', 'enterprise', 'Revoke a previously approved container image'),
    ('sbom.view', 'enterprise', 'View SBOM documents'),
    ('vulnerabilities.view', 'enterprise', 'View vulnerability scan results'),
    ('vulnerability_exceptions.request', 'enterprise', 'Request a vulnerability-policy exception'),
    ('vulnerability_exceptions.approve', 'enterprise', 'Approve a vulnerability-policy exception (dual control)')
ON CONFLICT DO NOTHING;

-- Enterprise Owner and Enterprise Administrator: every enterprise
-- permission (re-run of migration 0002's exact clause).
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'enterprise' AND r.key IN ('enterprise_owner', 'enterprise_admin')
  AND p.scope_type = 'enterprise'
ON CONFLICT DO NOTHING;

-- Read-Only Auditor: every enterprise *.view permission (re-run of
-- migration 0002's exact clause).
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'enterprise' AND r.key = 'read_only_auditor'
  AND (p.key LIKE '%.view' OR p.key = 'audit.view')
  AND p.scope_type = 'enterprise'
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'enterprise' AND r.key = 'ai_platform_engineer'
  AND p.key IN ('workloads.publish', 'models.edit', 'images.register', 'images.view',
                'vulnerability_exceptions.request', 'artefacts.view')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'enterprise' AND r.key = 'devops_engineer'
  AND p.key IN ('images.view', 'vulnerabilities.view', 'sbom.view')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'enterprise' AND r.key = 'data_engineer'
  AND p.key IN ('artefacts.view', 'artefacts.delete')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'enterprise' AND r.key = 'security_administrator'
  AND p.key IN ('images.approve', 'images.revoke', 'vulnerability_exceptions.approve',
                'sbom.view', 'vulnerabilities.view', 'workloads.retire')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'enterprise' AND r.key = 'compliance_manager'
  AND p.key IN ('models.approve', 'vulnerability_exceptions.approve', 'sbom.view',
                'vulnerabilities.view', 'artefacts.view')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'enterprise' AND r.key = 'application_owner'
  AND p.key IN ('workloads.publish', 'artefacts.view')
ON CONFLICT DO NOTHING;
