-- Milestone 4: Workload and Model Registry -- object-storage metadata for
-- artefacts (model weights, workload configs, raw SBOM documents, etc.)
-- held in the existing S3-compatible/MinIO abstraction.
--
-- `artefact_uploads` never stores the object's bytes or storage
-- credentials -- only metadata about an object GRIDKEEP itself named and
-- authorised (`internal/platform/storage` generates `object_key`
-- server-side as `tenants/{tenantID}/{uuid}` or
-- `tenants/{tenantID}/operators/{operatorID}/{uuid}`, so it is both
-- tenant/operator-isolated by construction and non-guessable -- never a
-- client-supplied path or filename). `status` tracks the
-- authorise-upload -> client-PUTs-to-a-signed-URL -> confirm-completion
-- lifecycle; nothing is trusted as "uploaded" until the completion step
-- verifies the object actually exists at the expected size/checksum via a
-- HEAD against the storage backend.
--
-- `artefact_access_grants` is the audit record of every signed URL this
-- system has ever issued (upload or download), independent of
-- `audit_events` -- "complete storage audit records" per the approved
-- architecture -- so a security review can answer "who was ever given a
-- URL to this object, and did they use it" without cross-referencing the
-- generic audit log's evidence blobs.

CREATE TABLE artefact_uploads (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id  UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    operator_id           UUID REFERENCES operators(id),
    object_key            TEXT NOT NULL UNIQUE,
    bucket                TEXT NOT NULL,
    purpose               TEXT NOT NULL CHECK (purpose IN ('workload_artefact', 'model_artefact', 'sbom_raw', 'other')),
    content_type          TEXT NOT NULL,
    content_length        BIGINT CHECK (content_length IS NULL OR content_length > 0),
    checksum_sha256       TEXT,
    status                TEXT NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending', 'uploaded', 'verified', 'failed', 'deleted')),
    malware_scan_status   TEXT NOT NULL DEFAULT 'not_scanned'
                          CHECK (malware_scan_status IN ('not_scanned', 'clean', 'infected', 'error')),
    version_id            TEXT,
    retention_policy      JSONB NOT NULL DEFAULT '{}'::jsonb,
    uploaded_by           UUID NOT NULL REFERENCES users(id),
    uploaded_at           TIMESTAMPTZ,
    deleted_by            UUID REFERENCES users(id),
    deleted_at            TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_artefact_uploads_tenant ON artefact_uploads(enterprise_tenant_id);
CREATE INDEX idx_artefact_uploads_operator ON artefact_uploads(operator_id);

ALTER TABLE artefact_uploads ENABLE ROW LEVEL SECURITY;
ALTER TABLE artefact_uploads FORCE ROW LEVEL SECURITY;
CREATE POLICY artefact_uploads_tenant_scope ON artefact_uploads
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY artefact_uploads_platform_bypass ON artefact_uploads
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE TABLE artefact_access_grants (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_tenant_id  UUID NOT NULL REFERENCES enterprise_tenants(id) ON DELETE CASCADE,
    artefact_upload_id    UUID NOT NULL REFERENCES artefact_uploads(id) ON DELETE CASCADE,
    granted_to            UUID NOT NULL REFERENCES users(id),
    action                TEXT NOT NULL CHECK (action IN ('upload', 'download')),
    expires_at            TIMESTAMPTZ NOT NULL,
    used_at               TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_artefact_access_grants_upload ON artefact_access_grants(artefact_upload_id);

ALTER TABLE artefact_access_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE artefact_access_grants FORCE ROW LEVEL SECURITY;
CREATE POLICY artefact_access_grants_tenant_scope ON artefact_access_grants
    USING (enterprise_tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY artefact_access_grants_platform_bypass ON artefact_access_grants
    USING (current_setting('app.platform_bypass', true) = 'true');
