-- Milestone 2: Operator and Infrastructure Registry -- technical inventory
-- layer (clusters, node pools, accelerators, storage, network capabilities).
--
-- Every table here carries operator_id directly (denormalized from its
-- parent cluster/site) rather than requiring a join, so its RLS policy can
-- be a simple, fast, self-contained comparison -- the same pattern every
-- operator-owned table in this schema already follows.
--
-- Every cluster/storage pool/network capability belongs to exactly one of a
-- data centre or an edge site (num_nonnulls constraint), never both and
-- never neither.

CREATE TABLE clusters (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id        UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    data_centre_id     UUID REFERENCES data_centres(id),
    edge_site_id       UUID REFERENCES edge_sites(id),
    name               TEXT NOT NULL,
    kubernetes_version TEXT NOT NULL DEFAULT '',
    status             TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'planned', 'maintenance', 'decommissioned')),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (num_nonnulls(data_centre_id, edge_site_id) = 1)
);
CREATE INDEX idx_clusters_operator ON clusters(operator_id);
CREATE INDEX idx_clusters_data_centre ON clusters(data_centre_id);
CREATE INDEX idx_clusters_edge_site ON clusters(edge_site_id);

ALTER TABLE clusters ENABLE ROW LEVEL SECURITY;
ALTER TABLE clusters FORCE ROW LEVEL SECURITY;
CREATE POLICY clusters_operator_scope ON clusters
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY clusters_platform_bypass ON clusters
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE TABLE node_pools (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id        UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    cluster_id         UUID NOT NULL REFERENCES clusters(id) ON DELETE CASCADE,
    name               TEXT NOT NULL,
    node_count         INT NOT NULL CHECK (node_count >= 0),
    cpu_cores_per_node INT NOT NULL CHECK (cpu_cores_per_node > 0),
    memory_gb_per_node INT NOT NULL CHECK (memory_gb_per_node > 0),
    status             TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'planned', 'decommissioned')),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_node_pools_operator ON node_pools(operator_id);
CREATE INDEX idx_node_pools_cluster ON node_pools(cluster_id);

ALTER TABLE node_pools ENABLE ROW LEVEL SECURITY;
ALTER TABLE node_pools FORCE ROW LEVEL SECURITY;
CREATE POLICY node_pools_operator_scope ON node_pools
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY node_pools_platform_bypass ON node_pools
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE TABLE accelerators (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id      UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    node_pool_id     UUID NOT NULL REFERENCES node_pools(id) ON DELETE CASCADE,
    accelerator_type TEXT NOT NULL,
    count_per_node   INT NOT NULL CHECK (count_per_node > 0),
    memory_gb        INT NOT NULL CHECK (memory_gb > 0),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_accelerators_operator ON accelerators(operator_id);
CREATE INDEX idx_accelerators_node_pool ON accelerators(node_pool_id);

ALTER TABLE accelerators ENABLE ROW LEVEL SECURITY;
ALTER TABLE accelerators FORCE ROW LEVEL SECURITY;
CREATE POLICY accelerators_operator_scope ON accelerators
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY accelerators_platform_bypass ON accelerators
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE TABLE storage_pools (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id       UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    data_centre_id    UUID REFERENCES data_centres(id),
    edge_site_id      UUID REFERENCES edge_sites(id),
    name              TEXT NOT NULL,
    storage_type      TEXT NOT NULL CHECK (storage_type IN ('block', 'object', 'file')),
    capacity_gb       BIGINT NOT NULL CHECK (capacity_gb > 0),
    encrypted_at_rest BOOLEAN NOT NULL DEFAULT TRUE,
    status            TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'planned', 'decommissioned')),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (num_nonnulls(data_centre_id, edge_site_id) = 1)
);
CREATE INDEX idx_storage_pools_operator ON storage_pools(operator_id);

ALTER TABLE storage_pools ENABLE ROW LEVEL SECURITY;
ALTER TABLE storage_pools FORCE ROW LEVEL SECURITY;
CREATE POLICY storage_pools_operator_scope ON storage_pools
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY storage_pools_platform_bypass ON storage_pools
    USING (current_setting('app.platform_bypass', true) = 'true');

CREATE TABLE network_capabilities (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id           UUID NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
    data_centre_id        UUID REFERENCES data_centres(id),
    edge_site_id          UUID REFERENCES edge_sites(id),
    capability_type       TEXT NOT NULL CHECK (capability_type IN ('private_5g', 'network_slice', 'low_latency_backbone', 'dedicated_fibre', 'public_internet_peering')),
    bandwidth_gbps        NUMERIC(10,2) NOT NULL CHECK (bandwidth_gbps > 0),
    estimated_latency_ms  NUMERIC(6,2),
    status                TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'planned', 'decommissioned')),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (num_nonnulls(data_centre_id, edge_site_id) = 1)
);
CREATE INDEX idx_network_capabilities_operator ON network_capabilities(operator_id);

ALTER TABLE network_capabilities ENABLE ROW LEVEL SECURITY;
ALTER TABLE network_capabilities FORCE ROW LEVEL SECURITY;
CREATE POLICY network_capabilities_operator_scope ON network_capabilities
    USING (operator_id = NULLIF(current_setting('app.operator_id', true), '')::uuid);
CREATE POLICY network_capabilities_platform_bypass ON network_capabilities
    USING (current_setting('app.platform_bypass', true) = 'true');
