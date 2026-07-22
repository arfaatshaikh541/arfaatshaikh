-- Security fix (post-Milestone-1 audit): enterprise_tenants and operators
-- had zero Row-Level Security, unlike every other tenant/operator-owned
-- table in this schema. Confirmed via direct psql access: with app.tenant_id
-- set to one tenant and app.platform_bypass left false, a plain SELECT
-- against enterprise_tenants still returned every tenant's row, relying
-- entirely on the application layer (internal/modules/rbac/middleware.go)
-- to prevent cross-tenant reads. This adds the same self-scope +
-- platform-bypass policy pair every membership/subscription table already
-- has, so a bug in the application-layer scope check is no longer the only
-- thing standing between one tenant/operator and another's profile row.

ALTER TABLE enterprise_tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE enterprise_tenants FORCE ROW LEVEL SECURITY;

CREATE POLICY enterprise_tenants_self_scope ON enterprise_tenants
    USING (id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

CREATE POLICY enterprise_tenants_platform_bypass ON enterprise_tenants
    USING (current_setting('app.platform_bypass', true) = 'true');

ALTER TABLE operators ENABLE ROW LEVEL SECURITY;
ALTER TABLE operators FORCE ROW LEVEL SECURITY;

CREATE POLICY operators_self_scope ON operators
    USING (id = NULLIF(current_setting('app.operator_id', true), '')::uuid);

CREATE POLICY operators_platform_bypass ON operators
    USING (current_setting('app.platform_bypass', true) = 'true');
