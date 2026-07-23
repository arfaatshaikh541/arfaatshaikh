// Package testutil provides a real-Postgres test database helper used by
// integration tests across every module. Tests in this codebase deliberately
// run against a real database rather than a mock -- RLS policies, triggers,
// and constraints are part of the system under test.
package testutil

import (
	"context"
	"os"
	"testing"

	dbpkg "gridkeep/control-api/internal/platform/db"
)

func testDatabaseURL() string {
	if v := os.Getenv("TEST_DATABASE_URL"); v != "" {
		return v
	}
	return "postgres://gridkeep:gridkeep_dev_password@localhost:5432/gridkeep_test?sslmode=disable"
}

// tablesToTruncate lists every table with data that could leak between
// tests, in an order safe for TRUNCATE ... CASCADE (CASCADE makes explicit
// ordering unnecessary, but the list is kept complete and explicit so a new
// migration's table is a deliberate addition here, not a silent gap).
var tablesToTruncate = []string{
	"audit_events",
	"attestation_results",
	"attestation_sessions",
	"attestation_policies",
	"deployment_events",
	"workload_secrets",
	"deployment_plans",
	"deployments",
	"deployment_plan_validations",
	"control_messages",
	"cluster_agent_certificates",
	"cluster_agents",
	"capacity_reservations",
	"placement_evaluations",
	"placement_requests",
	"capacity_offers",
	"workload_version_sboms",
	"workload_artefacts",
	"model_artefacts",
	"workload_health_checks",
	"workload_components",
	"workload_versions",
	"workloads",
	"artefact_access_grants",
	"artefact_uploads",
	"vulnerability_exceptions",
	"vulnerability_policies",
	"vulnerability_findings",
	"vulnerability_scans",
	"sboms",
	"image_provenance",
	"image_signatures",
	"container_images",
	"approved_container_registries",
	"model_deployment_profiles",
	"model_safety_evaluations",
	"model_benchmarks",
	"model_capabilities",
	"model_versions",
	"models",
	"model_licences",
	"model_providers",
	"policy_evaluation_records",
	"sovereignty_policies",
	"capacity_snapshots",
	"agent_certificates",
	"operator_agents",
	"network_capabilities",
	"storage_pools",
	"accelerators",
	"node_pools",
	"clusters",
	"data_centres",
	"edge_sites",
	"operator_contracts",
	"regions",
	"jurisdictions",
	"support_access_grants",
	"platform_role_assignments",
	"operator_subscriptions",
	"enterprise_subscriptions",
	"invitations",
	"operator_memberships",
	"operators",
	"enterprise_memberships",
	"enterprise_tenants",
	"mfa_challenges",
	"password_reset_tokens",
	"email_verification_tokens",
	"login_attempts",
	"mfa_totp_secrets",
	"sessions",
	"users",
}

// NewStore connects to the test database, applies all migrations (safe to
// call repeatedly), truncates every table so the test starts from a clean
// slate, and registers cleanup to close the pool.
func NewStore(t *testing.T) *dbpkg.Store {
	t.Helper()
	ctx := context.Background()

	store, err := dbpkg.Connect(ctx, testDatabaseURL())
	if err != nil {
		t.Fatalf("connect to test database (is Postgres running and TEST_DATABASE_URL set correctly?): %v", err)
	}
	t.Cleanup(func() { store.Close() })

	if _, err := store.Migrate(ctx); err != nil {
		t.Fatalf("migrate test database: %v", err)
	}

	if _, err := store.Pool.Exec(ctx, "TRUNCATE TABLE "+joinTables(tablesToTruncate)+" RESTART IDENTITY CASCADE"); err != nil {
		t.Fatalf("truncate test database: %v", err)
	}

	return store
}

func joinTables(tables []string) string {
	out := ""
	for i, t := range tables {
		if i > 0 {
			out += ", "
		}
		out += t
	}
	return out
}
