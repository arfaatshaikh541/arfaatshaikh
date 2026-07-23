-- Milestone 8: two new permission keys.
--
-- attestation.view (enterprise): the tenant's own "customer verification
-- view" of a deployment's attestation status -- always redacted (decision,
-- provider type, evaluated_at, reason codes only, never raw evidence or
-- measurements) regardless of this permission; see
-- internal/modules/attestation's package doc for why that redaction
-- happens at the handler layer, not via a separate permission tier.
--
-- operator.attestation.manage (operator): create/revoke confidential-computing
-- attestation policies for the operator's own clusters -- the operator is
-- this milestone's trust anchor for what its own hardware is expected to
-- report (see docs/project-status.md's Deliberate security decisions for
-- Milestone 8). Viewing attestation sessions/results for an operator's own
-- clusters requires only operator membership, mirroring Milestone 6's
-- cluster-agent control-message/validation history: view is membership,
-- manage/mutate is a permission.
INSERT INTO permissions (key, scope_type, description) VALUES
    ('attestation.view', 'enterprise', 'View a deployment attestation status (confidential computing)'),
    ('operator.attestation.manage', 'operator', 'Manage confidential-computing attestation policies for operator clusters')
ON CONFLICT DO NOTHING;

-- Enterprise Owner and Enterprise Administrator already receive every
-- enterprise permission via migration 0002's blanket grant, which does not
-- retroactively pick up permissions inserted later -- granted explicitly
-- here, same as every prior milestone's permissions migration.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'enterprise' AND r.key IN ('enterprise_owner', 'enterprise_admin')
  AND p.key = 'attestation.view'
ON CONFLICT DO NOTHING;

-- attestation.view is a read/verification capability tied to deployment
-- visibility -- granted to every role that already holds deployments.view
-- (ai_platform_engineer, application_owner, devops_engineer, read_only_auditor),
-- plus compliance_manager and security_administrator, for whom confirming a
-- confidential-computing deployment's attestation status is a direct part
-- of their existing compliance/security remit.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'enterprise'
  AND r.key IN ('ai_platform_engineer', 'application_owner', 'devops_engineer', 'read_only_auditor', 'compliance_manager', 'security_administrator')
  AND p.key = 'attestation.view'
ON CONFLICT DO NOTHING;

-- Operator Platform Owner already receives every operator permission via
-- migration 0002's blanket grant, same caveat as above.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'operator' AND r.key = 'operator_platform_owner'
  AND p.key = 'operator.attestation.manage'
ON CONFLICT DO NOTHING;

-- Operator Security Administrator manages attestation policies for the
-- same reason it already manages agent identity (operator.agents.manage):
-- attestation policy is a security-hardware-trust concern, not a general
-- infrastructure-capacity one.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'operator' AND r.key = 'operator_security_administrator'
  AND p.key = 'operator.attestation.manage'
ON CONFLICT DO NOTHING;
