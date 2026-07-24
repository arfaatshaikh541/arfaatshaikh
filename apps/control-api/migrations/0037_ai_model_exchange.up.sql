-- Milestone 13: AI Model Exchange.
--
-- The approved architecture's entity list for this milestone (ModelListing,
-- ModelLicence, ModelGeographyRestriction, ModelLanguageCapability,
-- ModelPricing, ModelDeploymentProfile, ModelProvider, ModelAccessGrant) is
-- overwhelmingly already built by Milestone 4's model registry: licence
-- terms, permitted/prohibited geographies, supported_languages, and
-- deployment profiles are already real columns/tables on
-- models/model_versions, and model_providers is already the platform-curated
-- provider vocabulary. What Milestone 4 never built is the cross-tenant
-- exchange on top of that registry -- every model_version has always been
-- readable only by the single enterprise_tenant_id that registered it.
--
-- This migration adds exactly the same shape Milestone 12 added for capacity:
-- a visibility flag (public/private) plus a per-tenant grant table for the
-- private case, and it is deliberately private-by-default (the opposite of
-- capacity_offers' public-by-default) since a model is normally an
-- enterprise's own asset until it deliberately chooses to list it on the
-- exchange. model_access_grants carries the same
-- price_per_unit_override-for-a-specific-tenant shape as
-- capacity_offer_grants, resolved and applied entirely server-side.
--
-- Structured pricing (price_per_unit/pricing_unit/currency) is new: the
-- existing pricing_metadata JSONB column is free-form vendor detail, not
-- something the exchange can compute a default listing price from. There is
-- no settlement integration this milestone -- the approved scope for
-- Milestone 13 lists "pricing" but not "settlement contracts" the way
-- Milestone 12 explicitly did, so this establishes the rate mechanism only,
-- the same order Milestone 5 established capacity pricing well before
-- Milestone 11's billing module arrived.
ALTER TABLE model_versions
    ADD COLUMN visibility TEXT NOT NULL DEFAULT 'private' CHECK (visibility IN ('public', 'private')),
    ADD COLUMN price_per_unit NUMERIC(14,6) CHECK (price_per_unit IS NULL OR price_per_unit >= 0),
    ADD COLUMN pricing_unit TEXT NOT NULL DEFAULT '',
    ADD COLUMN currency TEXT NOT NULL DEFAULT 'USD',
    ADD COLUMN published_at TIMESTAMPTZ,
    ADD CONSTRAINT model_versions_publish_requires_approval CHECK (visibility = 'private' OR status = 'approved');

-- model_access_grants is the per-tenant "invitation" a private model version
-- needs to be visible/selectable at all by another tenant's workloads --
-- identical shape and purpose to capacity_offer_grants (Milestone 12).
-- owner_tenant_id is denormalized from model_versions.enterprise_tenant_id
-- (not joined at RLS-evaluation time) for the same reason
-- capacity_offer_grants denormalizes operator_id: RLS policies compare
-- session variables against a plain column on the row being checked, not a
-- subquery into another RLS-protected table.
CREATE TABLE model_access_grants (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_version_id            UUID NOT NULL REFERENCES model_versions(id) ON DELETE CASCADE,
    owner_tenant_id              UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    grantee_tenant_id            UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    price_per_unit_override      NUMERIC(14,6) CHECK (price_per_unit_override IS NULL OR price_per_unit_override >= 0),
    status                       TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
    created_by                   UUID NOT NULL REFERENCES users(id),
    created_at                   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (model_version_id, grantee_tenant_id)
);
CREATE INDEX idx_model_access_grants_version ON model_access_grants(model_version_id);
CREATE INDEX idx_model_access_grants_grantee ON model_access_grants(grantee_tenant_id);

ALTER TABLE model_access_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_access_grants FORCE ROW LEVEL SECURITY;
CREATE POLICY model_access_grants_owner_scope ON model_access_grants
    USING (owner_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY model_access_grants_grantee_read ON model_access_grants
    FOR SELECT USING (grantee_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY model_access_grants_platform_bypass ON model_access_grants
    USING (current_setting('app.platform_bypass', true) = 'true');

-- Marketplace read: an additional PERMISSIVE SELECT policy alongside each
-- table's existing all-commands *_tenant_scope owner policy. Postgres ORs
-- permissive policies of the same command type together, so this does not
-- replace or narrow the owner's existing full access -- it only adds a
-- second way a row can become visible for SELECT, the same coexistence
-- bilateral_agreements_operator_scope (ALL) and bilateral_agreements_tenant_read
-- (SELECT) already rely on (Milestone 12).
CREATE POLICY model_versions_marketplace_read ON model_versions
    FOR SELECT
    USING (
        status = 'approved'
        AND (
            visibility = 'public'
            OR EXISTS (
                SELECT 1 FROM model_access_grants g
                WHERE g.model_version_id = model_versions.id
                  AND g.grantee_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
                  AND g.status = 'active'
            )
        )
    );

CREATE POLICY model_capabilities_marketplace_read ON model_capabilities
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM model_versions mv
            WHERE mv.id = model_capabilities.model_version_id
              AND mv.status = 'approved'
              AND (
                mv.visibility = 'public'
                OR EXISTS (
                    SELECT 1 FROM model_access_grants g
                    WHERE g.model_version_id = mv.id
                      AND g.grantee_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
                      AND g.status = 'active'
                )
              )
        )
    );

CREATE POLICY model_benchmarks_marketplace_read ON model_benchmarks
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM model_versions mv
            WHERE mv.id = model_benchmarks.model_version_id
              AND mv.status = 'approved'
              AND (
                mv.visibility = 'public'
                OR EXISTS (
                    SELECT 1 FROM model_access_grants g
                    WHERE g.model_version_id = mv.id
                      AND g.grantee_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
                      AND g.status = 'active'
                )
              )
        )
    );

CREATE POLICY model_safety_evaluations_marketplace_read ON model_safety_evaluations
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM model_versions mv
            WHERE mv.id = model_safety_evaluations.model_version_id
              AND mv.status = 'approved'
              AND (
                mv.visibility = 'public'
                OR EXISTS (
                    SELECT 1 FROM model_access_grants g
                    WHERE g.model_version_id = mv.id
                      AND g.grantee_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
                      AND g.status = 'active'
                )
              )
        )
    );

CREATE POLICY model_deployment_profiles_marketplace_read ON model_deployment_profiles
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM model_versions mv
            WHERE mv.id = model_deployment_profiles.model_version_id
              AND mv.status = 'approved'
              AND (
                mv.visibility = 'public'
                OR EXISTS (
                    SELECT 1 FROM model_access_grants g
                    WHERE g.model_version_id = mv.id
                      AND g.grantee_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
                      AND g.status = 'active'
                )
              )
        )
    );

-- Provider onboarding: model_providers was, until now, platform-curated
-- reference data with no create/lifecycle endpoint at all (seed-data only,
-- unlike jurisdictions/regions which already had real create endpoints since
-- Milestone 2). status follows the exact active/retired-shaped pattern
-- regions already established, renamed suspended/active to match a
-- commercial provider relationship rather than an infrastructure taxonomy
-- entry.
ALTER TABLE model_providers
    ADD COLUMN status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended')),
    ADD COLUMN onboarded_by UUID REFERENCES users(id);
