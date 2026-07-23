-- Milestone 4: Workload and Model Registry -- platform-curated model
-- catalogue vocabulary.
--
-- model_providers/model_licences are global reference data (which AI model
-- providers and which licence terms exist at all), the same role
-- jurisdictions/regions played for Milestone 2's operator taxonomy: every
-- authenticated user may read them, only a platform permission may write
-- them, and no RLS applies since there is no tenant/operator ownership to
-- enforce. Enterprises then register their OWN `models`/`model_versions`
-- rows (Milestone 4 step 2) that reference this shared vocabulary rather
-- than inventing free-text provider/licence names.

CREATE TABLE model_providers (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key         TEXT NOT NULL UNIQUE CHECK (key ~ '^[a-z0-9-]+$'),
    name        TEXT NOT NULL,
    website     TEXT NOT NULL DEFAULT '',
    notes       TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE model_licences (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key                         TEXT NOT NULL UNIQUE CHECK (key ~ '^[a-z0-9-]+$'),
    name                        TEXT NOT NULL,
    terms_url                   TEXT NOT NULL DEFAULT '',
    allows_commercial_use       BOOLEAN NOT NULL,
    allows_redistribution       BOOLEAN NOT NULL,
    notes                       TEXT NOT NULL DEFAULT '',
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- New platform permission for managing this catalogue, following the exact
-- precedent of platform.regions.manage (migration 0012): the
-- platform_super_administrator role's "every platform.* permission" grant
-- ran once in migration 0002 and does not retroactively apply to
-- permissions added afterward, so it must be granted explicitly here.
INSERT INTO permissions (key, scope_type, description) VALUES
    ('platform.model_catalogue.manage', 'platform', 'Manage the global model provider/licence catalogue')
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.scope_type = 'platform' AND r.key = 'platform_super_administrator'
  AND p.key = 'platform.model_catalogue.manage'
ON CONFLICT DO NOTHING;
