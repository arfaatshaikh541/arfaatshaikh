-- Milestone 4: Workload and Model Registry -- the workload registry itself.
--
-- `workloads` is the enterprise-owned, mutable header; `workload_versions`
-- is the immutable-once-published record of everything a specific version
-- guarantees. As with model_versions (migration 0019), several
-- architecture entities (WorkloadResourceRequirement, WorkloadNetwork-
-- Requirement, WorkloadStorageRequirement, WorkloadSecurityRequirement,
-- WorkloadResidencyRequirement, WorkloadScalingPolicy) are modeled as JSONB
-- columns rather than their own tables -- 1:1 facts about a single version,
-- not independently-lifecycled relationships.
--
-- Publish is dual-control, the same requested_by/approved_by +
-- self-approval CHECK constraint this codebase now applies consistently
-- (support_access_grants in Milestone 1, sovereignty_policies in Milestone
-- 3, model_versions above) -- a workload version cannot become "published"
-- (and therefore immutable and eligible to be referenced) without a second,
-- different user's sign-off.
--
-- Immutability itself is enforced in two layers, the same defense-in-depth
-- shape as everywhere else in this schema: the service layer
-- (Milestone 4 step 6) only permits edits while status = 'draft', and the
-- trigger below independently blocks any attempt to change a published
-- version's requirement/image/model columns at the database level even if
-- the application layer had a bug.
--
-- A workload version references its container image and model version by
-- foreign key to container_images.id/model_versions.id -- never by a raw
-- tag string -- so "deploy by immutable digest only" is structural, not
-- just a convention the application layer has to remember to enforce.

CREATE TABLE workloads (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id  UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    workload_key          TEXT NOT NULL,
    workload_type         TEXT NOT NULL CHECK (workload_type IN (
                              'containerised_inference_api', 'retrieval_augmented_generation_application',
                              'private_ai_assistant', 'computer_vision_inference', 'speech_to_text_service',
                              'text_to_speech_service', 'embedding_service', 'ai_agent_runtime',
                              'batch_inference', 'model_evaluation'
                          )),
    name                  TEXT NOT NULL,
    description           TEXT NOT NULL DEFAULT '',
    owner_user_id         UUID NOT NULL REFERENCES users(id),
    status                TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'retired')),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (enterprise_tenant_id, workload_key)
);
CREATE INDEX idx_workloads_tenant ON workloads(enterprise_tenant_id);

ALTER TABLE workloads ENABLE ROW LEVEL SECURITY;
ALTER TABLE workloads FORCE ROW LEVEL SECURITY;
CREATE POLICY workloads_tenant_scope ON workloads
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY workloads_platform_bypass ON workloads
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE TABLE workload_versions (
    id                              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workload_id                     UUID NOT NULL REFERENCES workloads(id) ON DELETE CASCADE,
    enterprise_tenant_id            UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    version                         INT NOT NULL CHECK (version > 0),
    status                          TEXT NOT NULL DEFAULT 'draft'
                                     CHECK (status IN ('draft', 'pending_publish', 'published', 'deprecated', 'retired')),
    container_image_id              UUID REFERENCES container_images(id),
    model_version_id                UUID REFERENCES model_versions(id),
    resource_requirements           JSONB NOT NULL DEFAULT '{}'::jsonb,
    network_requirements            JSONB NOT NULL DEFAULT '{}'::jsonb,
    storage_requirements            JSONB NOT NULL DEFAULT '{}'::jsonb,
    security_requirements           JSONB NOT NULL DEFAULT '{}'::jsonb,
    residency_requirements          JSONB NOT NULL DEFAULT '{}'::jsonb,
    scaling_policy                  JSONB NOT NULL DEFAULT '{}'::jsonb,
    retention_policy                JSONB NOT NULL DEFAULT '{}'::jsonb,
    deployment_approval_required    BOOLEAN NOT NULL DEFAULT TRUE,
    requested_by                    UUID NOT NULL REFERENCES users(id),
    approved_by                     UUID REFERENCES users(id),
    published_at                    TIMESTAMPTZ,
    retired_at                      TIMESTAMPTZ,
    retirement_reason               TEXT,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workload_id, version),
    CONSTRAINT workload_versions_no_self_approval CHECK (approved_by IS NULL OR approved_by <> requested_by)
);
CREATE INDEX idx_workload_versions_tenant ON workload_versions(enterprise_tenant_id);
CREATE INDEX idx_workload_versions_workload ON workload_versions(workload_id);

ALTER TABLE workload_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE workload_versions FORCE ROW LEVEL SECURITY;
CREATE POLICY workload_versions_tenant_scope ON workload_versions
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY workload_versions_platform_bypass ON workload_versions
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE FUNCTION workload_versions_block_published_mutation() RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status <> 'draft' AND OLD.status <> 'pending_publish' THEN
        IF NEW.container_image_id   IS DISTINCT FROM OLD.container_image_id  OR
           NEW.model_version_id      IS DISTINCT FROM OLD.model_version_id    OR
           NEW.resource_requirements IS DISTINCT FROM OLD.resource_requirements OR
           NEW.network_requirements  IS DISTINCT FROM OLD.network_requirements  OR
           NEW.storage_requirements  IS DISTINCT FROM OLD.storage_requirements  OR
           NEW.security_requirements IS DISTINCT FROM OLD.security_requirements OR
           NEW.residency_requirements IS DISTINCT FROM OLD.residency_requirements OR
           NEW.scaling_policy        IS DISTINCT FROM OLD.scaling_policy THEN
            RAISE EXCEPTION 'workload_versions: cannot modify a % version''s content', OLD.status;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER workload_versions_immutability
    BEFORE UPDATE ON workload_versions
    FOR EACH ROW EXECUTE FUNCTION workload_versions_block_published_mutation();

CREATE TABLE workload_components (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id  UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    workload_version_id   UUID NOT NULL REFERENCES workload_versions(id) ON DELETE CASCADE,
    component_key         TEXT NOT NULL,
    name                  TEXT NOT NULL,
    container_image_id    UUID NOT NULL REFERENCES container_images(id),
    command               JSONB NOT NULL DEFAULT '[]'::jsonb,
    args                  JSONB NOT NULL DEFAULT '[]'::jsonb,
    env                   JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_primary            BOOLEAN NOT NULL DEFAULT FALSE,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workload_version_id, component_key)
);
CREATE INDEX idx_workload_components_version ON workload_components(workload_version_id);

ALTER TABLE workload_components ENABLE ROW LEVEL SECURITY;
ALTER TABLE workload_components FORCE ROW LEVEL SECURITY;
CREATE POLICY workload_components_tenant_scope ON workload_components
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY workload_components_platform_bypass ON workload_components
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE TABLE workload_health_checks (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id    UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    workload_component_id   UUID NOT NULL REFERENCES workload_components(id) ON DELETE CASCADE,
    check_type              TEXT NOT NULL CHECK (check_type IN ('http', 'tcp', 'exec')),
    path                    TEXT NOT NULL DEFAULT '',
    port                    INT,
    command                 JSONB NOT NULL DEFAULT '[]'::jsonb,
    interval_seconds        INT NOT NULL DEFAULT 10 CHECK (interval_seconds > 0),
    timeout_seconds         INT NOT NULL DEFAULT 5 CHECK (timeout_seconds > 0),
    failure_threshold       INT NOT NULL DEFAULT 3 CHECK (failure_threshold > 0),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_workload_health_checks_component ON workload_health_checks(workload_component_id);

ALTER TABLE workload_health_checks ENABLE ROW LEVEL SECURITY;
ALTER TABLE workload_health_checks FORCE ROW LEVEL SECURITY;
CREATE POLICY workload_health_checks_tenant_scope ON workload_health_checks
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY workload_health_checks_platform_bypass ON workload_health_checks
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE TABLE workload_artefacts (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id  UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    workload_version_id   UUID NOT NULL REFERENCES workload_versions(id) ON DELETE CASCADE,
    artefact_upload_id    UUID NOT NULL REFERENCES artefact_uploads(id),
    role                  TEXT NOT NULL DEFAULT '',
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workload_version_id, artefact_upload_id)
);
CREATE INDEX idx_workload_artefacts_version ON workload_artefacts(workload_version_id);

ALTER TABLE workload_artefacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE workload_artefacts FORCE ROW LEVEL SECURITY;
CREATE POLICY workload_artefacts_tenant_scope ON workload_artefacts
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY workload_artefacts_platform_bypass ON workload_artefacts
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE TABLE model_artefacts (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id  UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    model_version_id      UUID NOT NULL REFERENCES model_versions(id) ON DELETE CASCADE,
    artefact_upload_id    UUID NOT NULL REFERENCES artefact_uploads(id),
    role                  TEXT NOT NULL DEFAULT '',
    checksum_sha256       TEXT NOT NULL DEFAULT '',
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (model_version_id, artefact_upload_id)
);
CREATE INDEX idx_model_artefacts_version ON model_artefacts(model_version_id);

ALTER TABLE model_artefacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_artefacts FORCE ROW LEVEL SECURITY;
CREATE POLICY model_artefacts_tenant_scope ON model_artefacts
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY model_artefacts_platform_bypass ON model_artefacts
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE TABLE workload_version_sboms (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id  UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    workload_version_id   UUID NOT NULL REFERENCES workload_versions(id) ON DELETE CASCADE,
    sbom_id               UUID NOT NULL REFERENCES sboms(id),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workload_version_id, sbom_id)
);
CREATE INDEX idx_workload_version_sboms_version ON workload_version_sboms(workload_version_id);

ALTER TABLE workload_version_sboms ENABLE ROW LEVEL SECURITY;
ALTER TABLE workload_version_sboms FORCE ROW LEVEL SECURITY;
CREATE POLICY workload_version_sboms_tenant_scope ON workload_version_sboms
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY workload_version_sboms_platform_bypass ON workload_version_sboms
    USING (current_setting('app.platform_bypass', true) = 'true');
