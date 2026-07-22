-- Milestone 1: telecom operators and memberships, RLS-scoped by operator_id.

CREATE TABLE operators (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    legal_name   TEXT NOT NULL,
    display_name TEXT NOT NULL,
    country      TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending_application'
                 CHECK (status IN ('pending_application', 'under_review', 'approved', 'active', 'suspended', 'offboarding', 'terminated')),
    trust_level  TEXT NOT NULL DEFAULT 'unverified' CHECK (trust_level IN ('unverified', 'verified', 'revoked')),
    is_fictional_demo_data BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE operator_memberships (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    operator_id  UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    role_id      UUID NOT NULL REFERENCES roles(id),
    status       TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'revoked')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, operator_id)
);
CREATE INDEX idx_operator_memberships_operator ON operator_memberships(operator_id);
CREATE INDEX idx_operator_memberships_user ON operator_memberships(user_id);

ALTER TABLE operator_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE operator_memberships FORCE ROW LEVEL SECURITY;

CREATE POLICY operator_memberships_operator_scope ON operator_memberships
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);

CREATE POLICY operator_memberships_platform_bypass ON operator_memberships
    USING (current_setting('app.platform_bypass', true) = 'true');
