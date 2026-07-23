# GRIDKEEP Permission Matrix (seeded ground truth)

This document is generated from the actual seeded `roles`/`permissions`/`role_permissions`
rows -- most from migration `0002_rbac.up.sql` (Milestone 1), plus `platform.regions.manage`
added by migration `0012_registry_locations.up.sql` (Milestone 2) -- it is not aspirational,
it is what the running system enforces today. Regenerate after any change to these with:

```sql
SELECT r.scope_type, r.key, r.name, string_agg(p.key, ', ' ORDER BY p.key)
FROM roles r
LEFT JOIN role_permissions rp ON rp.role_id = r.id
LEFT JOIN permissions p ON p.id = rp.permission_id
GROUP BY r.scope_type, r.key, r.name ORDER BY r.scope_type, r.key;
```

## Enterprise Roles

| Role | Permissions |
|---|---|
| **AI Platform Engineer** (`ai_platform_engineer`) | artefacts.download, artefacts.upload, capacity.view, deployments.rollback, deployments.view, models.register, models.view, policies.simulate, policies.view, regions.view, reservations.cancel, reservations.create, workloads.create, workloads.deploy, workloads.edit, workloads.scale, workloads.view |
| **Application Owner** (`application_owner`) | deployments.view, usage.view, workloads.create, workloads.deploy, workloads.edit, workloads.pause, workloads.scale, workloads.view |
| **Compliance Manager** (`compliance_manager`) | approvals.respond, approvals.view, audit.view, incidents.view, policies.simulate, policies.view |
| **Data Engineer** (`data_engineer`) | artefacts.download, artefacts.upload, models.view, workloads.view |
| **DevOps Engineer** (`devops_engineer`) | capacity.view, deployments.failover, deployments.rollback, deployments.view, incidents.view, infrastructure.view, regions.select, regions.view, reservations.cancel, reservations.create, workloads.deploy, workloads.pause, workloads.retry, workloads.scale, workloads.terminate, workloads.view |
| **Enterprise Administrator** (`enterprise_admin`) | approvals.respond, approvals.view, artefacts.download, artefacts.upload, audit.view, billing.view, capacity.view, credentials.manage, deployments.approve, deployments.failover, deployments.rollback, deployments.view, incidents.manage, incidents.view, infrastructure.view, integrations.manage, models.publish, models.register, models.retire, models.view, policies.approve, policies.create, policies.edit, policies.publish, policies.rollback, policies.simulate, policies.view, regions.select, regions.view, reservations.cancel, reservations.create, roles.manage, settings.manage, usage.view, users.manage, workloads.create, workloads.deploy, workloads.edit, workloads.pause, workloads.retry, workloads.scale, workloads.terminate, workloads.view |
| **Enterprise Owner** (`enterprise_owner`) | approvals.respond, approvals.view, artefacts.download, artefacts.upload, audit.view, billing.view, capacity.view, credentials.manage, deployments.approve, deployments.failover, deployments.rollback, deployments.view, incidents.manage, incidents.view, infrastructure.view, integrations.manage, models.publish, models.register, models.retire, models.view, policies.approve, policies.create, policies.edit, policies.publish, policies.rollback, policies.simulate, policies.view, regions.select, regions.view, reservations.cancel, reservations.create, roles.manage, settings.manage, usage.view, users.manage, workloads.create, workloads.deploy, workloads.edit, workloads.pause, workloads.retry, workloads.scale, workloads.terminate, workloads.view |
| **FinOps Manager** (`finops_manager`) | billing.view, capacity.view, reservations.cancel, reservations.create, usage.view |
| **Read-Only Auditor** (`read_only_auditor`) | approvals.view, audit.view, billing.view, capacity.view, deployments.view, incidents.view, infrastructure.view, models.view, policies.view, regions.view, usage.view, workloads.view |
| **Security Administrator** (`security_administrator`) | audit.view, credentials.manage, incidents.manage, incidents.view, integrations.manage, policies.approve, policies.create, policies.edit, policies.publish, policies.rollback, policies.simulate, policies.view, workloads.terminate |

## Operator Roles

| Role | Permissions |
|---|---|
| **Operator Auditor** (`operator_auditor`) | operator.audit.view, operator.deployments.view, operator.settlements.view, operator.usage.view |
| **Operator Capacity Manager** (`operator_capacity_manager`) | operator.capacity.manage, operator.deployments.view, operator.offerings.manage |
| **Operator Cloud Administrator** (`operator_cloud_administrator`) | operator.capacity.manage, operator.deployments.view, operator.regions.manage |
| **Operator Compliance Officer** (`operator_compliance_officer`) | operator.agreements.manage, operator.audit.view |
| **Operator Edge Administrator** (`operator_edge_administrator`) | operator.capacity.manage, operator.deployments.view, operator.locations.manage |
| **Operator Finance Manager** (`operator_finance_manager`) | operator.pricing.manage, operator.settlements.view, operator.usage.view |
| **Operator Infrastructure Administrator** (`operator_infrastructure_administrator`) | operator.capacity.manage, operator.clusters.manage, operator.deployments.view, operator.locations.manage |
| **Operator Network Administrator** (`operator_network_administrator`) | operator.deployments.view, operator.regions.manage |
| **Operator Platform Owner** (`operator_platform_owner`) | operator.agents.manage, operator.agreements.manage, operator.audit.view, operator.capacity.manage, operator.clusters.manage, operator.deployments.manage, operator.deployments.view, operator.incidents.manage, operator.locations.manage, operator.offerings.manage, operator.pricing.manage, operator.profile.manage, operator.regions.manage, operator.security.manage, operator.settlements.view, operator.sla.manage, operator.usage.view |
| **Operator Product Manager** (`operator_product_manager`) | operator.agreements.manage, operator.offerings.manage, operator.pricing.manage |
| **Operator Security Administrator** (`operator_security_administrator`) | operator.agents.manage, operator.audit.view, operator.incidents.manage, operator.security.manage |
| **Operator Support Engineer** (`operator_support_engineer`) | operator.deployments.view, operator.incidents.manage |

## Platform Roles

| Role | Permissions |
|---|---|
| **GRIDKEEP Auditor** (`platform_auditor`) | platform.audit.view, platform.billing.view, platform.security.view, platform.support_access.view |
| **GRIDKEEP Billing Administrator** (`platform_billing_administrator`) | platform.billing.manage, platform.billing.view |
| **GRIDKEEP Platform Operations Engineer** (`platform_operations_engineer`) | platform.feature_flags.manage, platform.releases.manage |
| **GRIDKEEP Security Operator** (`platform_security_operator`) | platform.audit.view, platform.security.view, platform.support_access.view |
| **GRIDKEEP Platform Super Administrator** (`platform_super_administrator`) | platform.audit.view, platform.billing.manage, platform.billing.view, platform.feature_flags.manage, platform.operators.manage, platform.regions.manage, platform.releases.manage, platform.security.view, platform.support_access.grant, platform.support_access.view, platform.tenants.manage |
| **GRIDKEEP Support Engineer** (`platform_support_engineer`) | platform.support_access.grant, platform.support_access.view |

## Notes

- Platform roles are granted only via `platform_role_assignments` -- never inherited
  from any enterprise or operator membership (see ADR 0002 and the support-access
  dual-control flow in `internal/modules/platformadmin`).
- A user with no membership and no active, approved support-access grant is denied
  regardless of any permission listed here -- the permission check only runs *after*
  scope resolution succeeds (see `internal/modules/rbac/middleware.go`).
- Permission keys for modules that do not exist yet (workloads, deployments, policies,
  models, reservations, capacity, incidents, approvals, ...) are seeded as durable product
  vocabulary but are not yet enforced by any route. They will be wired to real enforcement
  as their owning modules are built in later milestones.
- As of Milestone 2, `operator.regions.manage`, `operator.locations.manage`,
  `operator.clusters.manage`, `operator.profile.manage`, and `operator.agents.manage` are
  enforced for real by `internal/modules/registry` and `internal/modules/agents` (data
  centres, edge sites, clusters, node pools, accelerators, storage pools, network
  capabilities, operator contracts, and operator-agent registration/certificate lifecycle).
  `platform.regions.manage` (new in Milestone 2) gates writes to the global
  region/jurisdiction taxonomy; reading that taxonomy requires only an authenticated
  session, no specific permission, since it is non-sensitive shared reference data.
