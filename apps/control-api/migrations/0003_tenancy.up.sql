-- Milestone 1: enterprise tenants and memberships, with Row-Level Security
-- as a defense-in-depth backstop under application-level scope checks.

CREATE TABLE enterprise_tenants (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    legal_name   TEXT NOT NULL,
    display_name TEXT NOT NULL,
    country      TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'offboarding', 'terminated')),
    is_fictional_demo_data BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE enterprise_memberships (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id               UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    enterprise_tenant_id  UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    role_id               UUID NOT NULL REFERENCES roles(id),
    status                TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'revoked')),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, enterprise_tenant_id)
);
CREATE INDEX idx_enterprise_memberships_tenant ON enterprise_memberships(enterprise_tenant_id);
CREATE INDEX idx_enterprise_memberships_user ON enterprise_memberships(user_id);

ALTER TABLE enterprise_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE enterprise_memberships FORCE ROW LEVEL SECURITY;

CREATE POLICY enterprise_memberships_tenant_scope ON enterprise_memberships
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

CREATE POLICY enterprise_memberships_platform_bypass ON enterprise_memberships
    USING (current_setting('app.platform_bypass', true) = 'true');
