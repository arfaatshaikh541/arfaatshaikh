-- Milestone 1: subscription plans, features, and tenant/operator subscriptions.
-- Entitlements are resolved on demand (service layer) from active
-- subscription -> plan -> plan_features and cached briefly in Redis; there is
-- deliberately no separate persisted entitlements table yet, since a cache is
-- not a system of record and the source-of-truth join is inexpensive at
-- Milestone 1 scale.

CREATE TABLE features (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key         TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE subscription_plans (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key         TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    scope_type  TEXT NOT NULL CHECK (scope_type IN ('enterprise', 'operator')),
    description TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE plan_features (
    plan_id     UUID NOT NULL REFERENCES subscription_plans(id) ON DELETE CASCADE,
    feature_id  UUID NOT NULL REFERENCES features(id) ON DELETE CASCADE,
    limit_value JSONB,
    PRIMARY KEY (plan_id, feature_id)
);

CREATE TABLE enterprise_subscriptions (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id  UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    plan_id               UUID NOT NULL REFERENCES subscription_plans(id),
    status                TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'cancelled', 'expired')),
    started_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    ends_at               TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_enterprise_subscriptions_tenant ON enterprise_subscriptions(enterprise_tenant_id);

CREATE TABLE operator_subscriptions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id  UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    plan_id      UUID NOT NULL REFERENCES subscription_plans(id),
    status       TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'cancelled', 'expired')),
    started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    ends_at      TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_operator_subscriptions_operator ON operator_subscriptions(operator_id);

ALTER TABLE enterprise_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE enterprise_subscriptions FORCE ROW LEVEL SECURITY;
CREATE POLICY enterprise_subscriptions_tenant_scope ON enterprise_subscriptions
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY enterprise_subscriptions_platform_bypass ON enterprise_subscriptions
    USING (current_setting('app.platform_bypass', true) = 'true');

ALTER TABLE operator_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE operator_subscriptions FORCE ROW LEVEL SECURITY;
CREATE POLICY operator_subscriptions_operator_scope ON operator_subscriptions
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY operator_subscriptions_platform_bypass ON operator_subscriptions
    USING (current_setting('app.platform_bypass', true) = 'true');

-- ---------------------------------------------------------------------
-- Seed plans and features (product catalogue, not tenant data)
-- ---------------------------------------------------------------------
INSERT INTO features (key, name, description) VALUES
    ('max_users', 'Maximum users', 'Maximum number of active memberships'),
    ('max_workloads', 'Maximum workloads', 'Maximum number of workload definitions (future milestone enforcement)'),
    ('confidential_computing', 'Confidential computing', 'Access to confidential-computing placement (future milestone enforcement)'),
    ('federated_capacity', 'Federated capacity exchange', 'Access to cross-operator capacity federation (future milestone enforcement)')
ON CONFLICT DO NOTHING;

INSERT INTO subscription_plans (key, name, scope_type, description) VALUES
    ('enterprise_starter', 'Enterprise Starter', 'enterprise', 'Entry-level enterprise plan'),
    ('enterprise_growth', 'Enterprise Growth', 'enterprise', 'Mid-tier enterprise plan with higher limits'),
    ('enterprise_sovereign', 'Enterprise Sovereign', 'enterprise', 'Full-feature sovereign deployment plan'),
    ('operator_standard', 'Operator Standard', 'operator', 'Standard operator federation plan'),
    ('operator_premium', 'Operator Premium', 'operator', 'Premium operator federation plan with federated capacity')
ON CONFLICT DO NOTHING;

INSERT INTO plan_features (plan_id, feature_id, limit_value)
SELECT p.id, f.id, '5'::jsonb FROM subscription_plans p, features f
WHERE p.key = 'enterprise_starter' AND f.key = 'max_users'
ON CONFLICT DO NOTHING;

INSERT INTO plan_features (plan_id, feature_id, limit_value)
SELECT p.id, f.id, '50'::jsonb FROM subscription_plans p, features f
WHERE p.key = 'enterprise_growth' AND f.key = 'max_users'
ON CONFLICT DO NOTHING;

INSERT INTO plan_features (plan_id, feature_id, limit_value)
SELECT p.id, f.id, 'null'::jsonb FROM subscription_plans p, features f
WHERE p.key = 'enterprise_sovereign' AND f.key = 'max_users'
ON CONFLICT DO NOTHING;

INSERT INTO plan_features (plan_id, feature_id, limit_value)
SELECT p.id, f.id, 'true'::jsonb FROM subscription_plans p, features f
WHERE p.key = 'enterprise_sovereign' AND f.key = 'confidential_computing'
ON CONFLICT DO NOTHING;

INSERT INTO plan_features (plan_id, feature_id, limit_value)
SELECT p.id, f.id, 'true'::jsonb FROM subscription_plans p, features f
WHERE p.key = 'operator_premium' AND f.key = 'federated_capacity'
ON CONFLICT DO NOTHING;
