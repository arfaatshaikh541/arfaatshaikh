-- Milestone 1: role/permission vocabulary shared across enterprise,
-- operator, and platform scopes. Permission keys for modules that do not
-- exist yet (workloads, deployments, policies, ...) are seeded now because
-- the vocabulary is durable product surface even though enforcement of those
-- specific keys lands in later milestones (see docs/security/permission-matrix.md).

CREATE TABLE roles (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_type  TEXT NOT NULL CHECK (scope_type IN ('enterprise', 'operator', 'platform')),
    key         TEXT NOT NULL,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    is_system   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (scope_type, key)
);

CREATE TABLE permissions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key         TEXT NOT NULL UNIQUE,
    scope_type  TEXT NOT NULL CHECK (scope_type IN ('enterprise', 'operator', 'platform')),
    description TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE role_permissions (
    role_id       UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

-- ---------------------------------------------------------------------
-- Permission catalogue
-- ---------------------------------------------------------------------
INSERT INTO permissions (key, scope_type, description) VALUES
    ('workloads.view', 'enterprise', 'View workload definitions and versions'),
    ('workloads.create', 'enterprise', 'Create workload definitions and versions'),
    ('workloads.edit', 'enterprise', 'Edit draft workload definitions'),
    ('workloads.deploy', 'enterprise', 'Deploy a workload version'),
    ('workloads.scale', 'enterprise', 'Scale a running workload'),
    ('workloads.pause', 'enterprise', 'Pause a running workload'),
    ('workloads.terminate', 'enterprise', 'Terminate a workload deployment'),
    ('workloads.retry', 'enterprise', 'Retry a failed deployment'),
    ('deployments.view', 'enterprise', 'View deployment status and history'),
    ('deployments.approve', 'enterprise', 'Approve a pending deployment'),
    ('deployments.rollback', 'enterprise', 'Roll back a deployment revision'),
    ('deployments.failover', 'enterprise', 'Trigger a policy-governed failover'),
    ('policies.view', 'enterprise', 'View sovereignty policies'),
    ('policies.create', 'enterprise', 'Draft a new sovereignty policy'),
    ('policies.edit', 'enterprise', 'Edit a draft sovereignty policy'),
    ('policies.publish', 'enterprise', 'Publish a sovereignty policy (dual control)'),
    ('policies.approve', 'enterprise', 'Approve a policy publication or change'),
    ('policies.simulate', 'enterprise', 'Run policy simulation'),
    ('policies.rollback', 'enterprise', 'Roll back a published policy'),
    ('models.view', 'enterprise', 'View model registry entries'),
    ('models.register', 'enterprise', 'Register a new model or version'),
    ('models.publish', 'enterprise', 'Publish a model for use'),
    ('models.retire', 'enterprise', 'Retire a model'),
    ('artefacts.upload', 'enterprise', 'Upload workload/model artefacts'),
    ('artefacts.download', 'enterprise', 'Download workload/model artefacts'),
    ('regions.view', 'enterprise', 'View available regions'),
    ('regions.select', 'enterprise', 'Select regions for placement'),
    ('infrastructure.view', 'enterprise', 'View eligible infrastructure metadata'),
    ('capacity.view', 'enterprise', 'View capacity offers and estimates'),
    ('reservations.create', 'enterprise', 'Create a capacity reservation'),
    ('reservations.cancel', 'enterprise', 'Cancel a capacity reservation'),
    ('usage.view', 'enterprise', 'View usage records'),
    ('billing.view', 'enterprise', 'View invoices and billing'),
    ('approvals.view', 'enterprise', 'View pending approvals'),
    ('approvals.respond', 'enterprise', 'Approve or reject a pending approval'),
    ('incidents.view', 'enterprise', 'View incidents'),
    ('incidents.manage', 'enterprise', 'Manage incident response'),
    ('audit.view', 'enterprise', 'View tenant audit log'),
    ('integrations.manage', 'enterprise', 'Manage third-party integrations'),
    ('credentials.manage', 'enterprise', 'Manage tenant service credentials'),
    ('users.manage', 'enterprise', 'Manage tenant users and invitations'),
    ('roles.manage', 'enterprise', 'Assign tenant roles'),
    ('settings.manage', 'enterprise', 'Manage tenant settings')
ON CONFLICT DO NOTHING;

INSERT INTO permissions (key, scope_type, description) VALUES
    ('operator.profile.manage', 'operator', 'Manage operator profile'),
    ('operator.regions.manage', 'operator', 'Manage operator regions'),
    ('operator.locations.manage', 'operator', 'Manage operator data centres and edge sites'),
    ('operator.clusters.manage', 'operator', 'Manage operator Kubernetes clusters'),
    ('operator.capacity.manage', 'operator', 'Manage operator capacity offers'),
    ('operator.pricing.manage', 'operator', 'Manage operator pricing'),
    ('operator.sla.manage', 'operator', 'Manage operator SLAs'),
    ('operator.offerings.manage', 'operator', 'Manage operator capacity offerings'),
    ('operator.agreements.manage', 'operator', 'Manage operator-enterprise agreements'),
    ('operator.deployments.view', 'operator', 'View deployments onto operator infrastructure'),
    ('operator.deployments.manage', 'operator', 'Manage deployments onto operator infrastructure'),
    ('operator.incidents.manage', 'operator', 'Manage operator incidents'),
    ('operator.usage.view', 'operator', 'View operator usage'),
    ('operator.settlements.view', 'operator', 'View operator settlements'),
    ('operator.security.manage', 'operator', 'Manage operator security settings'),
    ('operator.audit.view', 'operator', 'View operator audit log'),
    ('operator.agents.manage', 'operator', 'Manage operator/cluster agents and certificates')
ON CONFLICT DO NOTHING;

INSERT INTO permissions (key, scope_type, description) VALUES
    ('platform.tenants.manage', 'platform', 'Administer enterprise tenants'),
    ('platform.operators.manage', 'platform', 'Administer telecom operators'),
    ('platform.support_access.grant', 'platform', 'Grant just-in-time support access'),
    ('platform.support_access.view', 'platform', 'View support access grants'),
    ('platform.billing.view', 'platform', 'View platform-wide billing events'),
    ('platform.billing.manage', 'platform', 'Manage platform-wide billing configuration'),
    ('platform.security.view', 'platform', 'View platform security events'),
    ('platform.audit.view', 'platform', 'View platform audit log'),
    ('platform.releases.manage', 'platform', 'Manage connector/agent/policy-engine release versions'),
    ('platform.feature_flags.manage', 'platform', 'Manage platform feature flags')
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------
-- Roles
-- ---------------------------------------------------------------------
INSERT INTO roles (scope_type, key, name, description) VALUES
    ('enterprise', 'enterprise_owner', 'Enterprise Owner', 'Full control over the enterprise tenant'),
    ('enterprise', 'enterprise_admin', 'Enterprise Administrator', 'Administers users, roles, and settings'),
    ('enterprise', 'ai_platform_engineer', 'AI Platform Engineer', 'Builds and deploys AI workloads'),
    ('enterprise', 'devops_engineer', 'DevOps Engineer', 'Operates deployments and infrastructure selection'),
    ('enterprise', 'data_engineer', 'Data Engineer', 'Manages data references and artefacts'),
    ('enterprise', 'security_administrator', 'Security Administrator', 'Manages policies, credentials, and incidents'),
    ('enterprise', 'compliance_manager', 'Compliance Manager', 'Reviews policy compliance and audit evidence'),
    ('enterprise', 'finops_manager', 'FinOps Manager', 'Manages usage, billing, and budgets'),
    ('enterprise', 'application_owner', 'Application Owner', 'Owns a specific workload'),
    ('enterprise', 'read_only_auditor', 'Read-Only Auditor', 'Read-only visibility across the tenant')
ON CONFLICT DO NOTHING;

INSERT INTO roles (scope_type, key, name, description) VALUES
    ('operator', 'operator_platform_owner', 'Operator Platform Owner', 'Full control over the operator account'),
    ('operator', 'operator_infrastructure_administrator', 'Operator Infrastructure Administrator', 'Manages clusters and node pools'),
    ('operator', 'operator_cloud_administrator', 'Operator Cloud Administrator', 'Manages operator cloud regions'),
    ('operator', 'operator_edge_administrator', 'Operator Edge Administrator', 'Manages operator edge sites'),
    ('operator', 'operator_network_administrator', 'Operator Network Administrator', 'Manages operator network capabilities'),
    ('operator', 'operator_security_administrator', 'Operator Security Administrator', 'Manages operator security and agents'),
    ('operator', 'operator_capacity_manager', 'Operator Capacity Manager', 'Manages capacity offers and reservations'),
    ('operator', 'operator_product_manager', 'Operator Product Manager', 'Manages offerings and agreements'),
    ('operator', 'operator_finance_manager', 'Operator Finance Manager', 'Manages pricing and settlements'),
    ('operator', 'operator_compliance_officer', 'Operator Compliance Officer', 'Reviews operator compliance'),
    ('operator', 'operator_auditor', 'Operator Auditor', 'Read-only visibility across the operator account'),
    ('operator', 'operator_support_engineer', 'Operator Support Engineer', 'Handles operator incidents')
ON CONFLICT DO NOTHING;

INSERT INTO roles (scope_type, key, name, description) VALUES
    ('platform', 'platform_super_administrator', 'GRIDKEEP Platform Super Administrator', 'Full platform administration'),
    ('platform', 'platform_security_operator', 'GRIDKEEP Security Operator', 'Monitors platform-wide security events'),
    ('platform', 'platform_operations_engineer', 'GRIDKEEP Platform Operations Engineer', 'Manages releases and feature flags'),
    ('platform', 'platform_support_engineer', 'GRIDKEEP Support Engineer', 'Grants just-in-time support access'),
    ('platform', 'platform_billing_administrator', 'GRIDKEEP Billing Administrator', 'Manages platform-wide billing'),
    ('platform', 'platform_auditor', 'GRIDKEEP Auditor', 'Read-only visibility across the platform')
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------
-- Role -> permission assignments
-- ---------------------------------------------------------------------

-- Enterprise Owner and Enterprise Administrator: every enterprise permission.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'enterprise' AND r.key IN ('enterprise_owner', 'enterprise_admin')
  AND p.scope_type = 'enterprise'
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'enterprise' AND r.key = 'ai_platform_engineer'
  AND p.key IN ('workloads.view','workloads.create','workloads.edit','workloads.deploy','workloads.scale',
                'deployments.view','deployments.rollback','models.view','models.register',
                'artefacts.upload','artefacts.download','regions.view','capacity.view',
                'reservations.create','reservations.cancel','policies.view','policies.simulate')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'enterprise' AND r.key = 'devops_engineer'
  AND p.key IN ('workloads.view','workloads.deploy','workloads.scale','workloads.pause','workloads.terminate',
                'workloads.retry','deployments.view','deployments.rollback','deployments.failover',
                'regions.view','regions.select','infrastructure.view','capacity.view',
                'reservations.create','reservations.cancel','incidents.view')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'enterprise' AND r.key = 'data_engineer'
  AND p.key IN ('workloads.view','artefacts.upload','artefacts.download','models.view')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'enterprise' AND r.key = 'security_administrator'
  AND p.key IN ('policies.view','policies.create','policies.edit','policies.publish','policies.approve',
                'policies.simulate','policies.rollback','credentials.manage','incidents.view','incidents.manage',
                'audit.view','integrations.manage','workloads.terminate')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'enterprise' AND r.key = 'compliance_manager'
  AND p.key IN ('policies.view','policies.simulate','approvals.view','approvals.respond','audit.view','incidents.view')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'enterprise' AND r.key = 'finops_manager'
  AND p.key IN ('usage.view','billing.view','reservations.create','reservations.cancel','capacity.view')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'enterprise' AND r.key = 'application_owner'
  AND p.key IN ('workloads.view','workloads.create','workloads.edit','workloads.deploy','workloads.scale',
                'workloads.pause','deployments.view','usage.view')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'enterprise' AND r.key = 'read_only_auditor'
  AND (p.key LIKE '%.view' OR p.key = 'audit.view')
  AND p.scope_type = 'enterprise'
ON CONFLICT DO NOTHING;

-- Operator Platform Owner: every operator permission.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'operator' AND r.key = 'operator_platform_owner' AND p.scope_type = 'operator'
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'operator' AND r.key = 'operator_infrastructure_administrator'
  AND p.key IN ('operator.clusters.manage','operator.locations.manage','operator.capacity.manage','operator.deployments.view')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'operator' AND r.key = 'operator_cloud_administrator'
  AND p.key IN ('operator.regions.manage','operator.capacity.manage','operator.deployments.view')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'operator' AND r.key = 'operator_edge_administrator'
  AND p.key IN ('operator.locations.manage','operator.capacity.manage','operator.deployments.view')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'operator' AND r.key = 'operator_network_administrator'
  AND p.key IN ('operator.regions.manage','operator.deployments.view')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'operator' AND r.key = 'operator_security_administrator'
  AND p.key IN ('operator.security.manage','operator.agents.manage','operator.audit.view','operator.incidents.manage')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'operator' AND r.key = 'operator_capacity_manager'
  AND p.key IN ('operator.capacity.manage','operator.offerings.manage','operator.deployments.view')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'operator' AND r.key = 'operator_product_manager'
  AND p.key IN ('operator.offerings.manage','operator.agreements.manage','operator.pricing.manage')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'operator' AND r.key = 'operator_finance_manager'
  AND p.key IN ('operator.pricing.manage','operator.settlements.view','operator.usage.view')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'operator' AND r.key = 'operator_compliance_officer'
  AND p.key IN ('operator.audit.view','operator.agreements.manage')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'operator' AND r.key = 'operator_auditor'
  AND (p.key LIKE '%.view')
  AND p.scope_type = 'operator'
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'operator' AND r.key = 'operator_support_engineer'
  AND p.key IN ('operator.incidents.manage','operator.deployments.view')
ON CONFLICT DO NOTHING;

-- Platform roles
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'platform' AND r.key = 'platform_super_administrator' AND p.scope_type = 'platform'
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'platform' AND r.key = 'platform_security_operator'
  AND p.key IN ('platform.security.view','platform.audit.view','platform.support_access.view')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'platform' AND r.key = 'platform_operations_engineer'
  AND p.key IN ('platform.releases.manage','platform.feature_flags.manage')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'platform' AND r.key = 'platform_support_engineer'
  AND p.key IN ('platform.support_access.grant','platform.support_access.view')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'platform' AND r.key = 'platform_billing_administrator'
  AND p.key IN ('platform.billing.view','platform.billing.manage')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'platform' AND r.key = 'platform_auditor'
  AND (p.key LIKE '%.view')
  AND p.scope_type = 'platform'
ON CONFLICT DO NOTHING;
