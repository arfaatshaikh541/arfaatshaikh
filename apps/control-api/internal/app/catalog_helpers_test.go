package app_test

import (
	"testing"

	dbpkg "gridkeep/control-api/internal/platform/db"
)

// seedModelLicence inserts directly into model_licences -- global reference
// data with no RLS and no HTTP-exposed write path of its own in this
// milestone (it is platform-curated catalogue data, the same role
// jurisdictions/regions played in Milestone 2), so tests seed it the same
// way they grant platform roles: a direct, unscoped SQL statement.
func seedModelLicence(t *testing.T, store *dbpkg.Store, key string, allowsCommercial bool) string {
	t.Helper()
	var id string
	err := store.Pool.QueryRow(t.Context(), `
		INSERT INTO model_licences (key, name, allows_commercial_use, allows_redistribution)
		VALUES ($1, $1, $2, true)
		ON CONFLICT (key) DO UPDATE SET name = EXCLUDED.name
		RETURNING id
	`, key, allowsCommercial).Scan(&id)
	if err != nil {
		t.Fatalf("seed model licence %s: %v", key, err)
	}
	return id
}

// seedApprovedRegistry inserts directly into approved_container_registries
// (also global, unRLS'd platform reference data) -- equivalent to what a
// platform_super_administrator would do via
// POST /api/v1/platform/container-registries.
func seedApprovedRegistry(t *testing.T, store *dbpkg.Store, host string) {
	t.Helper()
	_, err := store.Pool.Exec(t.Context(), `
		INSERT INTO approved_container_registries (registry_host)
		VALUES ($1)
		ON CONFLICT (registry_host) DO NOTHING
	`, host)
	if err != nil {
		t.Fatalf("seed approved registry %s: %v", host, err)
	}
}

// fakeDigest returns a syntactically valid sha256 digest string derived
// from seed, so tests can mint distinct, deterministic digests without
// hashing real bytes.
func fakeDigest(seed string) string {
	const hexChars = "0123456789abcdef"
	out := make([]byte, 64)
	for i := range out {
		out[i] = hexChars[int(seed[i%len(seed)])%16]
	}
	return "sha256:" + string(out)
}
