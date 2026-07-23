-- Milestone 3: sovereignty policies. A policy is versioned and immutable
-- once published (approved architecture §22): draft -> pending_publish ->
-- published -> superseded. Dual control is required to publish, mirroring
-- the exact requested_by/approved_by + no-self-approval pattern already
-- used for support_access_grants (migration 0006) -- one author drafts and
-- requests publish, a genuinely different user approves it.
--
-- policy_key groups every version of "the same policy" together (e.g. a
-- tenant's residency policy might go through versions 1, 2, 3...);
-- (enterprise_tenant_id, policy_key, version) is unique. document holds the
-- evaluatable content matching policy_engine's PolicyDocument schema
-- (residency/operators/confidential_computing/cross_border/encryption).

CREATE TABLE sovereignty_policies (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id  UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    policy_key            TEXT NOT NULL,
    version               INT NOT NULL CHECK (version > 0),
    status                TEXT NOT NULL DEFAULT 'draft'
                          CHECK (status IN ('draft', 'pending_publish', 'published', 'superseded')),
    name                  TEXT NOT NULL,
    document              JSONB NOT NULL,
    requested_by          UUID NOT NULL REFERENCES users(id),
    requested_publish_at  TIMESTAMPTZ,
    approved_by           UUID REFERENCES users(id),
    published_at          TIMESTAMPTZ,
    superseded_at         TIMESTAMPTZ,
    rolled_back_from_version INT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (enterprise_tenant_id, policy_key, version),
    CONSTRAINT sovereignty_policies_no_self_approval CHECK (approved_by IS NULL OR approved_by <> requested_by)
);
CREATE INDEX idx_sovereignty_policies_tenant ON sovereignty_policies(enterprise_tenant_id);
CREATE INDEX idx_sovereignty_policies_key ON sovereignty_policies(enterprise_tenant_id, policy_key);
-- At most one published version per (tenant, policy_key) at a time -- a new
-- publish must first mark the previous published version 'superseded'.
CREATE UNIQUE INDEX idx_sovereignty_policies_one_published
    ON sovereignty_policies(enterprise_tenant_id, policy_key)
    WHERE status = 'published';

ALTER TABLE sovereignty_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE sovereignty_policies FORCE ROW LEVEL SECURITY;

CREATE POLICY sovereignty_policies_tenant_scope ON sovereignty_policies
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

CREATE POLICY sovereignty_policies_platform_bypass ON sovereignty_policies
    USING (current_setting('app.platform_bypass', true) = 'true');
