-- Milestone 1: invitations, scoped to exactly one of enterprise or operator.

CREATE TABLE invitations (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id UUID REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    operator_id          UUID REFERENCES operators(id) ON DELETE CASCADE,
    email                CITEXT NOT NULL,
    role_id              UUID NOT NULL REFERENCES roles(id),
    invited_by           UUID NOT NULL REFERENCES users(id),
    token_hash           TEXT NOT NULL UNIQUE,
    status               TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'revoked', 'expired')),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at           TIMESTAMPTZ NOT NULL,
    accepted_at          TIMESTAMPTZ,
    CONSTRAINT invitations_exactly_one_scope CHECK (
        (enterprise_tenant_id IS NOT NULL AND operator_id IS NULL) OR
        (enterprise_tenant_id IS NULL AND operator_id IS NOT NULL)
    )
);
CREATE INDEX idx_invitations_enterprise_tenant ON invitations(enterprise_tenant_id);
CREATE INDEX idx_invitations_operator ON invitations(operator_id);
CREATE INDEX idx_invitations_email ON invitations(email);

ALTER TABLE invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE invitations FORCE ROW LEVEL SECURITY;

CREATE POLICY invitations_tenant_scope ON invitations
    USING (enterprise_tenant_id IS NOT NULL AND enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

CREATE POLICY invitations_operator_scope ON invitations
    USING (operator_id IS NOT NULL AND operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);

CREATE POLICY invitations_platform_bypass ON invitations
    USING (current_setting('app.platform_bypass', true) = 'true');

-- Invitation acceptance must also be readable, unauthenticated, by exact
-- raw-token lookup (the recipient has no session yet). That path never goes
-- through the RLS-scoped connection: the service uses a dedicated
-- unscoped lookup by token_hash executed with platform_bypass enabled,
-- exactly like the platform's own onboarding flows.
