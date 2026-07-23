-- Milestone 4: Workload and Model Registry -- container-image supply-chain
-- foundations (approved registries, immutable-digest images, signatures,
-- provenance, SBOMs, vulnerability scanning and policy).
--
-- approved_container_registries is platform-curated global reference data
-- (no RLS), the same role model_providers/jurisdictions play elsewhere --
-- which registry hostnames are trusted at all is a platform-level security
-- decision, not something an individual tenant can grant itself.
--
-- container_images is tenant-owned and keyed by (enterprise_tenant_id,
-- digest), never by tag: `digest` is a content hash pinned at registration
-- time, and `tag` is stored purely as human-readable, non-authoritative
-- metadata. Nothing in this schema or the workloads module (Milestone 4
-- step 5) resolves an image by tag -- see the CHECK on `digest`'s format.
--
-- vulnerability_policies is one row per tenant (a singleton, enforced by
-- the UNIQUE constraint on enterprise_tenant_id) rather than a version
-- history, since "the tenant's current vulnerability policy" is what gates
-- every image-approval decision going forward, not something that needs
-- point-in-time versioning the way a sovereignty policy does.
--
-- vulnerability_exceptions follows the same dual-control shape as Milestone
-- 3's sovereignty_policies and Milestone 4's model_versions -- a different
-- user must approve an exception than the one who requested it. "Expired"
-- is a derived read-time state (now() > expires_at), not a stored status,
-- so no background job is needed to keep it accurate.

CREATE TABLE approved_container_registries (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    registry_host  TEXT NOT NULL UNIQUE,
    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    notes          TEXT NOT NULL DEFAULT '',
    added_by       UUID REFERENCES users(id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO permissions (key, scope_type, description) VALUES
    ('platform.container_registries.manage', 'platform', 'Manage the platform-approved container registry allowlist')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'platform' AND r.key = 'platform_super_administrator'
  AND p.key = 'platform.container_registries.manage'
ON CONFLICT DO NOTHING;

CREATE TABLE container_images (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id  UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    registry_host         TEXT NOT NULL,
    repository            TEXT NOT NULL,
    digest                TEXT NOT NULL CHECK (digest ~ '^sha256:[a-f0-9]{64}$'),
    tag                   TEXT NOT NULL DEFAULT '',
    status                TEXT NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending', 'approved', 'blocked', 'revoked')),
    registered_by         UUID NOT NULL REFERENCES users(id),
    approved_by           UUID REFERENCES users(id),
    approved_at           TIMESTAMPTZ,
    revoked_at            TIMESTAMPTZ,
    revocation_reason     TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (enterprise_tenant_id, digest)
);
CREATE INDEX idx_container_images_tenant ON container_images(enterprise_tenant_id);

ALTER TABLE container_images ENABLE ROW LEVEL SECURITY;
ALTER TABLE container_images FORCE ROW LEVEL SECURITY;
CREATE POLICY container_images_tenant_scope ON container_images
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY container_images_platform_bypass ON container_images
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE TABLE image_signatures (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id  UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    container_image_id    UUID NOT NULL REFERENCES container_images(id) ON DELETE CASCADE,
    signer                TEXT NOT NULL,
    public_key_pem        TEXT NOT NULL,
    signature_base64      TEXT NOT NULL,
    status                TEXT NOT NULL CHECK (status IN ('verified', 'invalid')),
    signed_at             TIMESTAMPTZ,
    verified_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_image_signatures_image ON image_signatures(container_image_id);

ALTER TABLE image_signatures ENABLE ROW LEVEL SECURITY;
ALTER TABLE image_signatures FORCE ROW LEVEL SECURITY;
CREATE POLICY image_signatures_tenant_scope ON image_signatures
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY image_signatures_platform_bypass ON image_signatures
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE TABLE image_provenance (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id  UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    container_image_id    UUID NOT NULL UNIQUE REFERENCES container_images(id) ON DELETE CASCADE,
    builder               TEXT NOT NULL DEFAULT '',
    source_repository     TEXT NOT NULL DEFAULT '',
    build_commit          TEXT NOT NULL DEFAULT '',
    build_pipeline_url    TEXT NOT NULL DEFAULT '',
    attestation           JSONB NOT NULL DEFAULT '{}'::jsonb,
    recorded_by           UUID NOT NULL REFERENCES users(id),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_image_provenance_image ON image_provenance(container_image_id);

ALTER TABLE image_provenance ENABLE ROW LEVEL SECURITY;
ALTER TABLE image_provenance FORCE ROW LEVEL SECURITY;
CREATE POLICY image_provenance_tenant_scope ON image_provenance
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY image_provenance_platform_bypass ON image_provenance
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE TABLE sboms (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id  UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    container_image_id    UUID NOT NULL REFERENCES container_images(id) ON DELETE CASCADE,
    format                TEXT NOT NULL CHECK (format IN ('spdx', 'cyclonedx')),
    document              JSONB NOT NULL,
    generated_by          TEXT NOT NULL DEFAULT '',
    ingested_by           UUID NOT NULL REFERENCES users(id),
    ingested_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_sboms_image ON sboms(container_image_id);

ALTER TABLE sboms ENABLE ROW LEVEL SECURITY;
ALTER TABLE sboms FORCE ROW LEVEL SECURITY;
CREATE POLICY sboms_tenant_scope ON sboms
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY sboms_platform_bypass ON sboms
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE TABLE vulnerability_scans (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id  UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    container_image_id    UUID NOT NULL REFERENCES container_images(id) ON DELETE CASCADE,
    scanner               TEXT NOT NULL,
    scanned_at            TIMESTAMPTZ NOT NULL,
    summary               JSONB NOT NULL DEFAULT '{}'::jsonb,
    ingested_by           UUID NOT NULL REFERENCES users(id),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_vulnerability_scans_image ON vulnerability_scans(container_image_id);

ALTER TABLE vulnerability_scans ENABLE ROW LEVEL SECURITY;
ALTER TABLE vulnerability_scans FORCE ROW LEVEL SECURITY;
CREATE POLICY vulnerability_scans_tenant_scope ON vulnerability_scans
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY vulnerability_scans_platform_bypass ON vulnerability_scans
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE TABLE vulnerability_findings (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id   UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    vulnerability_scan_id  UUID NOT NULL REFERENCES vulnerability_scans(id) ON DELETE CASCADE,
    cve_id                 TEXT NOT NULL DEFAULT '',
    severity               TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low', 'none')),
    package_name           TEXT NOT NULL DEFAULT '',
    package_version        TEXT NOT NULL DEFAULT '',
    fixed_version          TEXT NOT NULL DEFAULT '',
    description            TEXT NOT NULL DEFAULT '',
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_vulnerability_findings_scan ON vulnerability_findings(vulnerability_scan_id);

ALTER TABLE vulnerability_findings ENABLE ROW LEVEL SECURITY;
ALTER TABLE vulnerability_findings FORCE ROW LEVEL SECURITY;
CREATE POLICY vulnerability_findings_tenant_scope ON vulnerability_findings
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY vulnerability_findings_platform_bypass ON vulnerability_findings
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE TABLE vulnerability_policies (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id   UUID NOT NULL UNIQUE REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    max_allowed_severity   TEXT NOT NULL DEFAULT 'medium'
                           CHECK (max_allowed_severity IN ('none', 'low', 'medium', 'high', 'critical')),
    block_unsigned_images  BOOLEAN NOT NULL DEFAULT TRUE,
    require_sbom           BOOLEAN NOT NULL DEFAULT TRUE,
    updated_by             UUID REFERENCES users(id),
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE vulnerability_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE vulnerability_policies FORCE ROW LEVEL SECURITY;
CREATE POLICY vulnerability_policies_tenant_scope ON vulnerability_policies
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY vulnerability_policies_platform_bypass ON vulnerability_policies
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE TABLE vulnerability_exceptions (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id  UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    container_image_id    UUID NOT NULL REFERENCES container_images(id) ON DELETE CASCADE,
    finding_id            UUID REFERENCES vulnerability_findings(id),
    requested_by          UUID NOT NULL REFERENCES users(id),
    reason                TEXT NOT NULL,
    requested_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    approved_by           UUID REFERENCES users(id),
    approved_at           TIMESTAMPTZ,
    expires_at            TIMESTAMPTZ NOT NULL,
    status                TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT vulnerability_exceptions_no_self_approval CHECK (approved_by IS NULL OR approved_by <> requested_by)
);
CREATE INDEX idx_vulnerability_exceptions_image ON vulnerability_exceptions(container_image_id);

ALTER TABLE vulnerability_exceptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE vulnerability_exceptions FORCE ROW LEVEL SECURITY;
CREATE POLICY vulnerability_exceptions_tenant_scope ON vulnerability_exceptions
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY vulnerability_exceptions_platform_bypass ON vulnerability_exceptions
    USING (current_setting('app.platform_bypass', true) = 'true');
