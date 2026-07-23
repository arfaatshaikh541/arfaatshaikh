-- Milestone 2: Operator and Infrastructure Registry -- location layer.
--
-- jurisdictions/regions are a platform-curated, global taxonomy shared by
-- every operator and (in a later milestone) the sovereignty policy engine --
-- an operator selects from this vocabulary rather than inventing its own
-- region names, so cross-operator policy statements like "EU regions only"
-- stay meaningful. Like `roles`/`permissions`, this is global reference
-- data with no tenant/operator ownership, so no RLS applies to it; every
-- authenticated user may read it, only platform.regions.manage may write it.
--
-- operator_contracts/data_centres/edge_sites are operator-owned and follow
-- the same self-scope + platform-bypass RLS pattern as every other
-- operator-owned table introduced in Milestone 1.

CREATE TABLE jurisdictions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    country_code TEXT NOT NULL UNIQUE CHECK (country_code ~ '^[A-Z]{2}$'),
    name         TEXT NOT NULL,
    notes        TEXT NOT NULL DEFAULT '',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE regions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key             TEXT NOT NULL UNIQUE CHECK (key ~ '^[a-z0-9-]+$'),
    name            TEXT NOT NULL,
    jurisdiction_id UUID NOT NULL REFERENCES jurisdictions(id),
    status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'retired')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_regions_jurisdiction ON regions(jurisdiction_id);

CREATE TABLE operator_contracts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id         UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    contract_reference  TEXT NOT NULL,
    effective_at        TIMESTAMPTZ NOT NULL,
    terminates_at       TIMESTAMPTZ,
    status              TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'terminated')),
    notes               TEXT NOT NULL DEFAULT '',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (terminates_at IS NULL OR terminates_at > effective_at)
);
CREATE INDEX idx_operator_contracts_operator ON operator_contracts(operator_id);

ALTER TABLE operator_contracts ENABLE ROW LEVEL SECURITY;
ALTER TABLE operator_contracts FORCE ROW LEVEL SECURITY;

CREATE POLICY operator_contracts_operator_scope ON operator_contracts
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);

CREATE POLICY operator_contracts_platform_bypass ON operator_contracts
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE TABLE data_centres (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id  UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    region_id    UUID NOT NULL REFERENCES regions(id),
    name         TEXT NOT NULL,
    locality     TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'planned', 'decommissioned')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_data_centres_operator ON data_centres(operator_id);
CREATE INDEX idx_data_centres_region ON data_centres(region_id);

ALTER TABLE data_centres ENABLE ROW LEVEL SECURITY;
ALTER TABLE data_centres FORCE ROW LEVEL SECURITY;

CREATE POLICY data_centres_operator_scope ON data_centres
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);

CREATE POLICY data_centres_platform_bypass ON data_centres
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE TABLE edge_sites (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id  UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    region_id    UUID NOT NULL REFERENCES regions(id),
    name         TEXT NOT NULL,
    locality     TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'planned', 'decommissioned')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_edge_sites_operator ON edge_sites(operator_id);
CREATE INDEX idx_edge_sites_region ON edge_sites(region_id);

ALTER TABLE edge_sites ENABLE ROW LEVEL SECURITY;
ALTER TABLE edge_sites FORCE ROW LEVEL SECURITY;

CREATE POLICY edge_sites_operator_scope ON edge_sites
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);

CREATE POLICY edge_sites_platform_bypass ON edge_sites
    USING (current_setting('app.platform_bypass', true) = 'true');

-- New platform permission for managing the global region/jurisdiction
-- taxonomy -- granted automatically to platform_super_administrator only
-- (that role's existing "every platform.* permission" grant was executed
-- by migration 0002 and does not retroactively pick up permissions added
-- later, so it is granted explicitly here).
INSERT INTO permissions (key, scope_type, description) VALUES
    ('platform.regions.manage', 'platform', 'Manage the global region/jurisdiction taxonomy')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'platform' AND r.key = 'platform_super_administrator'
  AND p.key = 'platform.regions.manage'
ON CONFLICT DO NOTHING;
