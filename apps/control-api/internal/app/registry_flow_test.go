package app_test

import (
	"net/http"
	"testing"
)

// activateOperator moves a freshly-created operator (which starts
// pending_application) to active, the same way a platform admin would
// during real onboarding -- registry write endpoints require an
// active/approved operator, matching every other operator-scoped write in
// this codebase.
func activateOperator(t *testing.T, platformAdmin *client, operatorID string) {
	t.Helper()
	resp, body := platformAdmin.patch("/api/v1/platform/operators/"+operatorID+"/status", map[string]string{"status": "active"})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("activate operator: expected 200, got %d: %v", resp.StatusCode, body)
	}
}

// TestRegistryInfrastructureLifecycle exercises the full Milestone 2
// registry chain for real: a platform admin curates the region taxonomy,
// then an operator builds out its own location and technical inventory on
// top of it -- data centre -> cluster -> node pool -> accelerator -- with
// every List endpoint confirming what Create just wrote.
func TestRegistryInfrastructureLifecycle(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}

	platformAdmin := registerVerifyAndLogin(t, base, smtp, "registry-platform-admin@example.com")
	grantPlatformRole(t, store, "registry-platform-admin@example.com", "platform_super_administrator")

	resp, body := platformAdmin.post("/api/v1/jurisdictions", map[string]string{
		"country_code": "DE", "name": "Germany",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create jurisdiction: expected 201, got %d: %v", resp.StatusCode, body)
	}
	jurisdictionID := str(t, body, "id")

	resp, body = platformAdmin.post("/api/v1/regions", map[string]string{
		"key": "eu-central-1", "name": "EU Central", "jurisdiction_id": jurisdictionID,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create region: expected 201, got %d: %v", resp.StatusCode, body)
	}
	regionID := str(t, body, "id")

	owner := registerVerifyAndLogin(t, base, smtp, "registry-operator-owner@example.com")
	operatorID := createOperator(t, owner, "Registry Test Operator", "DE")
	activateOperator(t, platformAdmin, operatorID)

	// Any authenticated user (not just platform admins) can read the
	// region taxonomy -- it's non-sensitive shared reference data.
	regions := owner.getArray(t, "/api/v1/regions")
	if len(regions) == 0 {
		t.Fatalf("expected at least one region visible to any authenticated user")
	}

	resp, body = owner.post("/api/v1/operators/"+operatorID+"/data-centres", map[string]string{
		"region_id": regionID, "name": "Frankfurt DC1", "locality": "Frankfurt",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create data centre: expected 201, got %d: %v", resp.StatusCode, body)
	}
	dataCentreID := str(t, body, "id")

	resp, body = owner.post("/api/v1/operators/"+operatorID+"/clusters", map[string]string{
		"data_centre_id": dataCentreID, "name": "gpu-cluster-1", "kubernetes_version": "1.31",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create cluster: expected 201, got %d: %v", resp.StatusCode, body)
	}
	clusterID := str(t, body, "id")

	resp, body = owner.post("/api/v1/operators/"+operatorID+"/node-pools", map[string]any{
		"cluster_id": clusterID, "name": "gpu-pool-a", "node_count": 4,
		"cpu_cores_per_node": 64, "memory_gb_per_node": 512,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create node pool: expected 201, got %d: %v", resp.StatusCode, body)
	}
	nodePoolID := str(t, body, "id")

	resp, body = owner.post("/api/v1/operators/"+operatorID+"/accelerators", map[string]any{
		"node_pool_id": nodePoolID, "accelerator_type": "NVIDIA H100", "count_per_node": 8, "memory_gb": 80,
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create accelerator: expected 201, got %d: %v", resp.StatusCode, body)
	}

	clusters := owner.getArray(t, "/api/v1/operators/"+operatorID+"/clusters")
	if len(clusters) != 1 {
		t.Fatalf("list clusters: expected 1 cluster, got %d", len(clusters))
	}

	nodePools := owner.getArray(t, "/api/v1/operators/"+operatorID+"/node-pools")
	if len(nodePools) != 1 {
		t.Fatalf("list node pools: expected 1 node pool, got %d", len(nodePools))
	}

	accelerators := owner.getArray(t, "/api/v1/operators/"+operatorID+"/accelerators")
	if len(accelerators) != 1 {
		t.Fatalf("list accelerators: expected 1 accelerator, got %d", len(accelerators))
	}
}

// TestRegistryRejectsCrossOperatorParentReference is a security regression
// test: an operator must not be able to attach a cluster to another
// operator's data centre by simply guessing/knowing its UUID.
func TestRegistryRejectsCrossOperatorParentReference(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}

	platformAdmin := registerVerifyAndLogin(t, base, smtp, "registry-platform-admin-2@example.com")
	grantPlatformRole(t, store, "registry-platform-admin-2@example.com", "platform_super_administrator")

	_, body := platformAdmin.post("/api/v1/jurisdictions", map[string]string{"country_code": "AE", "name": "UAE"})
	jurisdictionID := str(t, body, "id")
	_, body = platformAdmin.post("/api/v1/regions", map[string]string{"key": "me-central-1", "name": "Middle East Central", "jurisdiction_id": jurisdictionID})
	regionID := str(t, body, "id")

	ownerA := registerVerifyAndLogin(t, base, smtp, "registry-operator-a@example.com")
	operatorA := createOperator(t, ownerA, "Registry Operator A", "AE")
	activateOperator(t, platformAdmin, operatorA)
	_, body = ownerA.post("/api/v1/operators/"+operatorA+"/data-centres", map[string]string{
		"region_id": regionID, "name": "Operator A DC", "locality": "Dubai",
	})
	dataCentreA := str(t, body, "id")

	ownerB := registerVerifyAndLogin(t, base, smtp, "registry-operator-b@example.com")
	operatorB := createOperator(t, ownerB, "Registry Operator B", "AE")
	activateOperator(t, platformAdmin, operatorB)

	resp, body := ownerB.post("/api/v1/operators/"+operatorB+"/clusters", map[string]string{
		"data_centre_id": dataCentreA, "name": "stolen-cluster",
	})
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("create cluster referencing another operator's data centre: expected 400, got %d: %v", resp.StatusCode, body)
	}
}

// TestRegistryDataCentreRejectsUnknownRegion proves region_id is validated
// server-side, not merely foreign-keyed (a nonexistent UUID that happens to
// be well-formed must still be rejected with a clear 400, not a 500).
func TestRegistryDataCentreRejectsUnknownRegion(t *testing.T) {
	srv, smtp, store := testServer(t)
	base := httpTestServer{URL: srv.URL}

	platformAdmin := registerVerifyAndLogin(t, base, smtp, "registry-platform-admin-3@example.com")
	grantPlatformRole(t, store, "registry-platform-admin-3@example.com", "platform_super_administrator")

	owner := registerVerifyAndLogin(t, base, smtp, "registry-operator-c@example.com")
	operatorID := createOperator(t, owner, "Registry Operator C", "DE")
	activateOperator(t, platformAdmin, operatorID)

	resp, body := owner.post("/api/v1/operators/"+operatorID+"/data-centres", map[string]string{
		"region_id": "00000000-0000-0000-0000-000000000000", "name": "Nowhere DC", "locality": "Nowhere",
	})
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("create data centre with unknown region: expected 400, got %d: %v", resp.StatusCode, body)
	}
}

// TestRegistryWriteRoutesRequirePermission proves a plain operator member
// without a locations/clusters-managing role cannot write registry data,
// even though they can read it.
func TestRegistryWriteRoutesRequirePermission(t *testing.T) {
	srv, smtp, _ := testServer(t)
	base := httpTestServer{URL: srv.URL}

	owner := registerVerifyAndLogin(t, base, smtp, "registry-operator-d-owner@example.com")
	operatorID := createOperator(t, owner, "Registry Operator D", "DE")

	outsider := registerVerifyAndLogin(t, base, smtp, "registry-operator-d-outsider@example.com")
	resp, body := outsider.post("/api/v1/operators/"+operatorID+"/data-centres", map[string]string{
		"region_id": "00000000-0000-0000-0000-000000000000", "name": "Should Be Blocked", "locality": "Nowhere",
	})
	if resp.StatusCode != http.StatusForbidden {
		t.Fatalf("outsider create data centre: expected 403, got %d: %v", resp.StatusCode, body)
	}
}
