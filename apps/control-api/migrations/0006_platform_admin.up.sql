-- Milestone 1: platform-role separation and just-in-time support access.
-- Platform roles are never inherited from enterprise/operator memberships;
-- they are granted explicitly and independently.

CREATE TABLE platform_role_assignments (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id     UUID NOT NULL REFERENCES roles(id),
    status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
    granted_by  UUID REFERENCES users(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, role_id)
);
CREATE INDEX idx_platform_role_assignments_user ON platform_role_assignments(user_id);

-- Support access grants: just-in-time, time-boxed, dual-control access for
-- platform staff into a specific enterprise or operator scope. No platform
-- role implicitly grants this; every session must be individually requested,
-- approved by someone other than the requester, time-limited, and audited.
CREATE TABLE support_access_grants (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scope_type    TEXT NOT NULL CHECK (scope_type IN ('enterprise', 'operator')),
    scope_id      UUID NOT NULL,
    reason        TEXT NOT NULL,
    requested_by  UUID NOT NULL REFERENCES users(id),
    approved_by   UUID REFERENCES users(id),
    approved_at   TIMESTAMPTZ,
    revoked_at    TIMESTAMPTZ,
    revoked_by    UUID REFERENCES users(id),
    expires_at    TIMESTAMPTZ NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT support_access_grants_no_self_approval CHECK (approved_by IS NULL OR approved_by <> requested_by)
);
CREATE INDEX idx_support_access_grants_scope ON support_access_grants(scope_type, scope_id);
CREATE INDEX idx_support_access_grants_user ON support_access_grants(user_id);
