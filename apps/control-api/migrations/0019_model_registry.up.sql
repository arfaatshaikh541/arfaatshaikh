-- Milestone 4: Workload and Model Registry -- the AI model registry itself.
--
-- `models` is the enterprise-owned, mutable header (name, description,
-- default provider); `model_versions` is the immutable-once-approved record
-- of everything a specific version of that model guarantees (checksum,
-- signature status, provenance, licence, permitted/prohibited geographies,
-- supported languages/hardware, retention behaviour, pricing). Every
-- version freezes its own copy of provider_id at creation time rather than
-- following `models.provider_id` live, since a model's declared provider
-- could change after a version was already approved and that version's
-- historical record must not silently change underneath it.
--
-- Several "entities" from the approved architecture (ModelRegionRestriction,
-- ModelHardwareRequirement, ModelRetentionPolicy) are modeled as JSONB
-- columns on model_versions rather than their own tables -- they are 1:1
-- facts about a single version, not independently-lifecycled many:many
-- relationships, exactly the same reasoning Milestone 3 applied to
-- PolicyDocument's constraint sub-objects. ModelCapability, ModelBenchmark,
-- ModelSafetyEvaluation, and ModelDeploymentProfile get real tables because
-- they are genuinely many-per-version with their own timestamps/content.
--
-- Approval is dual-control, the same requested_by/approved_by +
-- self-approval CHECK constraint pattern as Milestone 3's
-- sovereignty_policies -- a model version cannot become "approved" (usable
-- by a workload) without a second, different user's sign-off.

CREATE TABLE models (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id  UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    model_key             TEXT NOT NULL,
    name                  TEXT NOT NULL,
    description           TEXT NOT NULL DEFAULT '',
    provider_id           UUID REFERENCES model_providers(id),
    status                TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'retired')),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (enterprise_tenant_id, model_key)
);
CREATE INDEX idx_models_tenant ON models(enterprise_tenant_id);

ALTER TABLE models ENABLE ROW LEVEL SECURITY;
ALTER TABLE models FORCE ROW LEVEL SECURITY;
CREATE POLICY models_tenant_scope ON models
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY models_platform_bypass ON models
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE TABLE model_versions (
    id                              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id                        UUID NOT NULL REFERENCES models(id) ON DELETE CASCADE,
    enterprise_tenant_id            UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    version                         INT NOT NULL CHECK (version > 0),
    status                          TEXT NOT NULL DEFAULT 'draft'
                                     CHECK (status IN ('draft', 'pending_approval', 'approved', 'rejected', 'retired', 'revoked')),
    provider_id                     UUID REFERENCES model_providers(id),
    licence_id                      UUID NOT NULL REFERENCES model_licences(id),
    checksum_sha256                 TEXT NOT NULL DEFAULT '',
    signature_status                TEXT NOT NULL DEFAULT 'unsigned'
                                     CHECK (signature_status IN ('unsigned', 'signed_verified', 'signed_invalid')),
    provenance                      JSONB NOT NULL DEFAULT '{}'::jsonb,
    permitted_geographies           JSONB NOT NULL DEFAULT '[]'::jsonb,
    prohibited_geographies          JSONB NOT NULL DEFAULT '[]'::jsonb,
    supported_workload_types        JSONB NOT NULL DEFAULT '[]'::jsonb,
    supported_languages             JSONB NOT NULL DEFAULT '[]'::jsonb,
    hardware_requirements           JSONB NOT NULL DEFAULT '{}'::jsonb,
    minimum_accelerator_memory_gb   INT,
    security_profile                JSONB NOT NULL DEFAULT '{}'::jsonb,
    performance_metadata             JSONB NOT NULL DEFAULT '{}'::jsonb,
    input_types                     JSONB NOT NULL DEFAULT '[]'::jsonb,
    output_types                    JSONB NOT NULL DEFAULT '[]'::jsonb,
    retention_policy                 JSONB NOT NULL DEFAULT '{}'::jsonb,
    pricing_metadata                 JSONB NOT NULL DEFAULT '{}'::jsonb,
    requested_by                    UUID NOT NULL REFERENCES users(id),
    approved_by                     UUID REFERENCES users(id),
    approved_at                     TIMESTAMPTZ,
    rejected_reason                 TEXT,
    retired_at                      TIMESTAMPTZ,
    retirement_reason               TEXT,
    revoked_at                      TIMESTAMPTZ,
    revocation_reason               TEXT,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (model_id, version),
    CONSTRAINT model_versions_no_self_approval CHECK (approved_by IS NULL OR approved_by <> requested_by)
);
CREATE INDEX idx_model_versions_tenant ON model_versions(enterprise_tenant_id);
CREATE INDEX idx_model_versions_model ON model_versions(model_id);

ALTER TABLE model_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_versions FORCE ROW LEVEL SECURITY;
CREATE POLICY model_versions_tenant_scope ON model_versions
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY model_versions_platform_bypass ON model_versions
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE TABLE model_capabilities (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id  UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    model_version_id      UUID NOT NULL REFERENCES model_versions(id) ON DELETE CASCADE,
    capability_key        TEXT NOT NULL,
    description           TEXT NOT NULL DEFAULT '',
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (model_version_id, capability_key)
);
CREATE INDEX idx_model_capabilities_version ON model_capabilities(model_version_id);

ALTER TABLE model_capabilities ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_capabilities FORCE ROW LEVEL SECURITY;
CREATE POLICY model_capabilities_tenant_scope ON model_capabilities
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY model_capabilities_platform_bypass ON model_capabilities
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE TABLE model_benchmarks (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id  UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    model_version_id      UUID NOT NULL REFERENCES model_versions(id) ON DELETE CASCADE,
    benchmark_name        TEXT NOT NULL,
    metric_name           TEXT NOT NULL,
    metric_value          NUMERIC NOT NULL,
    evaluated_at          TIMESTAMPTZ NOT NULL,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_model_benchmarks_version ON model_benchmarks(model_version_id);

ALTER TABLE model_benchmarks ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_benchmarks FORCE ROW LEVEL SECURITY;
CREATE POLICY model_benchmarks_tenant_scope ON model_benchmarks
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY model_benchmarks_platform_bypass ON model_benchmarks
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE TABLE model_safety_evaluations (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id  UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    model_version_id      UUID NOT NULL REFERENCES model_versions(id) ON DELETE CASCADE,
    evaluator             TEXT NOT NULL,
    methodology           TEXT NOT NULL DEFAULT '',
    result                TEXT NOT NULL CHECK (result IN ('pass', 'fail', 'conditional')),
    findings              JSONB NOT NULL DEFAULT '{}'::jsonb,
    evaluated_at          TIMESTAMPTZ NOT NULL,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_model_safety_evaluations_version ON model_safety_evaluations(model_version_id);

ALTER TABLE model_safety_evaluations ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_safety_evaluations FORCE ROW LEVEL SECURITY;
CREATE POLICY model_safety_evaluations_tenant_scope ON model_safety_evaluations
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY model_safety_evaluations_platform_bypass ON model_safety_evaluations
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE TABLE model_deployment_profiles (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id  UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    model_version_id      UUID NOT NULL REFERENCES model_versions(id) ON DELETE CASCADE,
    profile_key           TEXT NOT NULL,
    name                  TEXT NOT NULL,
    resource_requirements JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (model_version_id, profile_key)
);
CREATE INDEX idx_model_deployment_profiles_version ON model_deployment_profiles(model_version_id);

ALTER TABLE model_deployment_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_deployment_profiles FORCE ROW LEVEL SECURITY;
CREATE POLICY model_deployment_profiles_tenant_scope ON model_deployment_profiles
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY model_deployment_profiles_platform_bypass ON model_deployment_profiles
    USING (current_setting('app.platform_bypass', true) = 'true');
