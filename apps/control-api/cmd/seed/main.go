// Command seed populates the local development database with clearly
// labeled FICTIONAL demo data: operators, enterprise tenants, users, and
// memberships. Every seeded operator/tenant row sets
// is_fictional_demo_data = true, and the UI displays a "Fictional demo
// data" badge wherever that flag is set. This must never be run against a
// production database -- it is gated by CONTROL_API_ENV below.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"github.com/google/uuid"

	dbpkg "gridkeep/control-api/internal/platform/db"
	"gridkeep/control-api/internal/platform/policyengine"
	"gridkeep/control-api/internal/platform/security"
)

// demoPassword is intentionally simple and identical for every seeded
// account. It is published in docs/project-status.md as a known, fictional,
// local-development-only credential -- never treat it as a secret and never
// reuse it anywhere real.
const demoPassword = "GridkeepDemo!2026"

type demoUser struct {
	email string
	id    uuid.UUID
}

func main() {
	ctx := context.Background()

	// Allowlist, not denylist: seeding known-password demo accounts
	// (including a Platform Super Administrator) is only ever safe in an
	// explicitly-named local/test environment. Blocking just the literal
	// string "production" would let any other misconfigured value --
	// "prod", "staging", "Production", an unset variable typo'd by a
	// deploy script -- sail through and seed those accounts into a real
	// environment.
	env := os.Getenv("CONTROL_API_ENV")
	if env != "development" && env != "test" {
		fmt.Fprintf(os.Stderr, "refusing to seed fictional demo data: CONTROL_API_ENV=%q is not an allowed local/test environment (must be exactly \"development\" or \"test\")\n", env)
		os.Exit(1)
	}

	databaseURL := os.Getenv("DATABASE_URL")
	if databaseURL == "" {
		fmt.Fprintln(os.Stderr, "DATABASE_URL is required")
		os.Exit(1)
	}

	store, err := dbpkg.Connect(ctx, databaseURL)
	if err != nil {
		fatal("connect to database", err)
	}
	defer store.Close()

	if _, err := store.Migrate(ctx); err != nil {
		fatal("run migrations", err)
	}

	hasher := security.NewPasswordHasher(65536, 3, 2)
	passwordHash, err := hasher.Hash(demoPassword)
	if err != nil {
		fatal("hash demo password", err)
	}

	// PlatformBypass is required here: enterprise_memberships,
	// operator_memberships, enterprise_subscriptions, and
	// operator_subscriptions all enforce Row-Level Security, and the seed
	// script -- like the platform-administration routes -- legitimately
	// needs to write across every tenant/operator in one transaction.
	tx, err := store.BeginScoped(ctx, dbpkg.Scope{PlatformBypass: true})
	if err != nil {
		fatal("begin transaction", err)
	}
	defer func() { _ = tx.Rollback(ctx) }()

	users := map[string]demoUser{}
	seedUser := func(email string) {
		var id uuid.UUID
		err := tx.QueryRow(ctx, `
			INSERT INTO users (email, password_hash, email_verified_at, mfa_enabled)
			VALUES ($1, $2, now(), false)
			ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash
			RETURNING id
		`, email, passwordHash).Scan(&id)
		if err != nil {
			fatal(fmt.Sprintf("seed user %s", email), err)
		}
		users[email] = demoUser{email: email, id: id}
	}

	platformAdminEmail := "platform-admin@gridkeep.io"
	falconOwnerEmail := "owner@falcon-national-bank.demo.gridkeep.io"
	falconComplianceEmail := "compliance@falcon-national-bank.demo.gridkeep.io"
	atlasOwnerEmail := "owner@atlas-gov.demo.gridkeep.io"
	helixOwnerEmail := "owner@helix-manufacturing.demo.gridkeep.io"
	gulfHorizonOwnerEmail := "owner@gulf-horizon-telecom.demo.gridkeep.io"
	euroNorthOwnerEmail := "owner@euronorth-communications.demo.gridkeep.io"

	for _, email := range []string{
		platformAdminEmail, falconOwnerEmail, falconComplianceEmail, atlasOwnerEmail, helixOwnerEmail,
		gulfHorizonOwnerEmail, euroNorthOwnerEmail,
	} {
		seedUser(email)
	}

	// Platform super administrator.
	if _, err := tx.Exec(ctx, `
		INSERT INTO platform_role_assignments (user_id, role_id)
		SELECT $1, id FROM roles WHERE scope_type = 'platform' AND key = 'platform_super_administrator'
		ON CONFLICT (user_id, role_id) DO NOTHING
	`, users[platformAdminEmail].id); err != nil {
		fatal("assign platform super administrator role", err)
	}

	// --- Enterprise tenants -------------------------------------------------
	// enterprise_tenants has no unique constraint on legal_name (two real
	// tenants could coincidentally share a legal name), so idempotency here
	// is enforced by an explicit look-up-then-insert rather than
	// ON CONFLICT, which would silently do nothing without ever detecting a
	// "conflict" and so would insert a fresh duplicate row on every re-run.
	tenantID := func(legalName, displayName, country, ownerEmail, planKey string) uuid.UUID {
		var id uuid.UUID
		err := tx.QueryRow(ctx, `SELECT id FROM enterprise_tenants WHERE legal_name = $1`, legalName).Scan(&id)
		if err != nil {
			err = tx.QueryRow(ctx, `
				INSERT INTO enterprise_tenants (legal_name, display_name, country, is_fictional_demo_data)
				VALUES ($1, $2, $3, true)
				RETURNING id
			`, legalName, displayName, country).Scan(&id)
			if err != nil {
				fatal(fmt.Sprintf("seed tenant %s", legalName), err)
			}
		}

		var ownerRoleID uuid.UUID
		if err := tx.QueryRow(ctx, `SELECT id FROM roles WHERE scope_type = 'enterprise' AND key = 'enterprise_owner'`).Scan(&ownerRoleID); err != nil {
			fatal("resolve enterprise_owner role", err)
		}
		if _, err := tx.Exec(ctx, `
			INSERT INTO enterprise_memberships (user_id, enterprise_tenant_id, role_id)
			VALUES ($1, $2, $3)
			ON CONFLICT (user_id, enterprise_tenant_id) DO NOTHING
		`, users[ownerEmail].id, id, ownerRoleID); err != nil {
			fatal(fmt.Sprintf("seed membership for %s", legalName), err)
		}

		var planID uuid.UUID
		if err := tx.QueryRow(ctx, `SELECT id FROM subscription_plans WHERE key = $1`, planKey).Scan(&planID); err != nil {
			fatal("resolve plan "+planKey, err)
		}
		if _, err := tx.Exec(ctx, `
			INSERT INTO enterprise_subscriptions (enterprise_tenant_id, plan_id)
			SELECT $1, $2 WHERE NOT EXISTS (
				SELECT 1 FROM enterprise_subscriptions WHERE enterprise_tenant_id = $1 AND status = 'active'
			)
		`, id, planID); err != nil {
			fatal(fmt.Sprintf("seed subscription for %s", legalName), err)
		}

		return id
	}

	falconTenantID := tenantID("Falcon National Bank Demo", "Falcon National Bank Demo", "AE", falconOwnerEmail, "enterprise_sovereign")
	tenantID("Atlas Government Services Demo", "Atlas Government Services Demo", "AE", atlasOwnerEmail, "enterprise_sovereign")
	tenantID("Helix Manufacturing Demo", "Helix Manufacturing Demo", "DE", helixOwnerEmail, "enterprise_growth")

	// A second Falcon National Bank member with the enterprise_admin role --
	// exists so the published sovereignty policy below has a genuine,
	// different approver on record (dual control, same as a real publish
	// would require through the API).
	var falconAdminRoleID uuid.UUID
	if err := tx.QueryRow(ctx, `SELECT id FROM roles WHERE scope_type = 'enterprise' AND key = 'enterprise_admin'`).Scan(&falconAdminRoleID); err != nil {
		fatal("resolve enterprise_admin role", err)
	}
	if _, err := tx.Exec(ctx, `
		INSERT INTO enterprise_memberships (user_id, enterprise_tenant_id, role_id)
		VALUES ($1, $2, $3)
		ON CONFLICT (user_id, enterprise_tenant_id) DO NOTHING
	`, users[falconComplianceEmail].id, falconTenantID, falconAdminRoleID); err != nil {
		fatal("seed compliance membership for Falcon National Bank Demo", err)
	}

	// --- Operators -----------------------------------------------------------
	operatorID := func(legalName, displayName, country, ownerEmail, planKey string) uuid.UUID {
		var id uuid.UUID
		err := tx.QueryRow(ctx, `SELECT id FROM operators WHERE legal_name = $1`, legalName).Scan(&id)
		if err != nil {
			err = tx.QueryRow(ctx, `
				INSERT INTO operators (legal_name, display_name, country, status, trust_level, is_fictional_demo_data)
				VALUES ($1, $2, $3, 'active', 'verified', true)
				RETURNING id
			`, legalName, displayName, country).Scan(&id)
			if err != nil {
				fatal(fmt.Sprintf("seed operator %s", legalName), err)
			}
		}

		var ownerRoleID uuid.UUID
		if err := tx.QueryRow(ctx, `SELECT id FROM roles WHERE scope_type = 'operator' AND key = 'operator_platform_owner'`).Scan(&ownerRoleID); err != nil {
			fatal("resolve operator_platform_owner role", err)
		}
		if _, err := tx.Exec(ctx, `
			INSERT INTO operator_memberships (user_id, operator_id, role_id)
			VALUES ($1, $2, $3)
			ON CONFLICT (user_id, operator_id) DO NOTHING
		`, users[ownerEmail].id, id, ownerRoleID); err != nil {
			fatal(fmt.Sprintf("seed membership for %s", legalName), err)
		}

		var planID uuid.UUID
		if err := tx.QueryRow(ctx, `SELECT id FROM subscription_plans WHERE key = $1`, planKey).Scan(&planID); err != nil {
			fatal("resolve plan "+planKey, err)
		}
		if _, err := tx.Exec(ctx, `
			INSERT INTO operator_subscriptions (operator_id, plan_id)
			SELECT $1, $2 WHERE NOT EXISTS (
				SELECT 1 FROM operator_subscriptions WHERE operator_id = $1 AND status = 'active'
			)
		`, id, planID); err != nil {
			fatal(fmt.Sprintf("seed subscription for %s", legalName), err)
		}

		return id
	}

	gulfHorizonID := operatorID("Gulf Horizon Telecom Demo", "Gulf Horizon Telecom Demo", "AE", gulfHorizonOwnerEmail, "operator_premium")
	euroNorthID := operatorID("EuroNorth Communications Demo", "EuroNorth Communications Demo", "DE", euroNorthOwnerEmail, "operator_standard")

	// --- Infrastructure registry (Milestone 2) -------------------------------
	jurisdictionID := func(countryCode, name string) uuid.UUID {
		var id uuid.UUID
		err := tx.QueryRow(ctx, `SELECT id FROM jurisdictions WHERE country_code = $1`, countryCode).Scan(&id)
		if err != nil {
			err = tx.QueryRow(ctx, `
				INSERT INTO jurisdictions (country_code, name) VALUES ($1, $2) RETURNING id
			`, countryCode, name).Scan(&id)
			if err != nil {
				fatal("seed jurisdiction "+countryCode, err)
			}
		}
		return id
	}
	regionID := func(key, name string, jurisdictionID uuid.UUID) uuid.UUID {
		var id uuid.UUID
		err := tx.QueryRow(ctx, `SELECT id FROM regions WHERE key = $1`, key).Scan(&id)
		if err != nil {
			err = tx.QueryRow(ctx, `
				INSERT INTO regions (key, name, jurisdiction_id) VALUES ($1, $2, $3) RETURNING id
			`, key, name, jurisdictionID).Scan(&id)
			if err != nil {
				fatal("seed region "+key, err)
			}
		}
		return id
	}
	dataCentreID := func(operatorID, regionID uuid.UUID, name, locality string) uuid.UUID {
		var id uuid.UUID
		err := tx.QueryRow(ctx, `SELECT id FROM data_centres WHERE operator_id = $1 AND name = $2`, operatorID, name).Scan(&id)
		if err != nil {
			err = tx.QueryRow(ctx, `
				INSERT INTO data_centres (operator_id, region_id, name, locality) VALUES ($1, $2, $3, $4) RETURNING id
			`, operatorID, regionID, name, locality).Scan(&id)
			if err != nil {
				fatal("seed data centre "+name, err)
			}
		}
		return id
	}
	clusterID := func(operatorID, dataCentreID uuid.UUID, name, k8sVersion string) uuid.UUID {
		var id uuid.UUID
		err := tx.QueryRow(ctx, `SELECT id FROM clusters WHERE operator_id = $1 AND name = $2`, operatorID, name).Scan(&id)
		if err != nil {
			err = tx.QueryRow(ctx, `
				INSERT INTO clusters (operator_id, data_centre_id, name, kubernetes_version) VALUES ($1, $2, $3, $4) RETURNING id
			`, operatorID, dataCentreID, name, k8sVersion).Scan(&id)
			if err != nil {
				fatal("seed cluster "+name, err)
			}
		}
		return id
	}

	aeJurisdiction := jurisdictionID("AE", "United Arab Emirates")
	deJurisdiction := jurisdictionID("DE", "Germany")
	meCentral := regionID("me-central-1", "Middle East Central", aeJurisdiction)
	euCentral := regionID("eu-central-1", "EU Central", deJurisdiction)

	gulfDataCentre := dataCentreID(gulfHorizonID, meCentral, "Dubai DC1", "Dubai")
	gulfClusterID := clusterID(gulfHorizonID, gulfDataCentre, "gulf-horizon-gpu-cluster-1", "1.31")

	euroNorthDataCentre := dataCentreID(euroNorthID, euCentral, "Frankfurt DC1", "Frankfurt")
	euroNorthClusterID := clusterID(euroNorthID, euroNorthDataCentre, "euronorth-gpu-cluster-1", "1.31")

	// --- Sovereignty policy (Milestone 3) ------------------------------------
	// A single already-published policy, inserted directly rather than
	// through the request-publish/approve-publish HTTP flow (this script
	// runs outside the API, with RLS bypassed) but recording the same
	// requested_by/approved_by dual-control facts a real publish would.
	falconResidencyDocument := policyengine.PolicyDocument{
		Residency: policyengine.ResidencyConstraint{
			AllowedCountries: []string{"AE"},
			DeniedCountries:  []string{},
		},
		Operators: policyengine.OperatorConstraint{Allowed: []string{}, Denied: []string{}},
		ConfidentialComputing: policyengine.ConfidentialComputingConstraint{
			Required: true,
		},
		CrossBorder: policyengine.CrossBorderConstraint{
			BackupAllowedCountries:   []string{"AE"},
			FailoverAllowedCountries: []string{},
		},
		Encryption: policyengine.EncryptionConstraint{},
	}
	falconDocumentJSON, err := json.Marshal(falconResidencyDocument)
	if err != nil {
		fatal("marshal Falcon residency policy document", err)
	}
	var existingPolicyID uuid.UUID
	err = tx.QueryRow(ctx, `
		SELECT id FROM sovereignty_policies
		WHERE enterprise_tenant_id = $1 AND policy_key = $2 AND status = 'published'
	`, falconTenantID, "data-residency").Scan(&existingPolicyID)
	if err != nil {
		if _, err := tx.Exec(ctx, `
			INSERT INTO sovereignty_policies (
				enterprise_tenant_id, policy_key, version, status, name, document,
				requested_by, requested_publish_at, approved_by, published_at
			)
			VALUES ($1, $2, 1, 'published', $3, $4, $5, now(), $6, now())
		`, falconTenantID, "data-residency", "UAE Data Residency", falconDocumentJSON,
			users[falconOwnerEmail].id, users[falconComplianceEmail].id); err != nil {
			fatal("seed Falcon National Bank sovereignty policy", err)
		}
	}

	// --- Workload and Model Registry (Milestone 4) --------------------------
	// All fictional: a made-up model provider/licence catalogue, one
	// approved container registry, one already-approved image, one
	// already-approved model version, and one already-published workload
	// version referencing both -- inserted directly (like the sovereignty
	// policy above) rather than through the request/approve HTTP flow, but
	// recording the same requested_by/approved_by dual-control facts a real
	// approval would. No real object bytes exist for the seeded artefact --
	// this environment's MinIO is not reachable in this sandboxed session
	// (see internal/platform/storage's commit message) -- so its row is
	// fictional metadata only, clearly not a substitute for exercising the
	// real upload/download flow.
	fakeDigest := func(seed string) string {
		hex := "0123456789abcdef"
		var b strings.Builder
		for i := 0; i < 64; i++ {
			b.WriteByte(hex[int(seed[i%len(seed)])%16])
		}
		return "sha256:" + b.String()
	}

	if _, err := tx.Exec(ctx, `
		INSERT INTO approved_container_registries (registry_host, notes, added_by)
		VALUES ('registry.gridkeep-demo.io', 'Fictional demo registry', $1)
		ON CONFLICT (registry_host) DO NOTHING
	`, users[platformAdminEmail].id); err != nil {
		fatal("seed approved container registry", err)
	}

	var providerID uuid.UUID
	if err := tx.QueryRow(ctx, `
		INSERT INTO model_providers (key, name, website)
		VALUES ('fictional-ai-labs', 'Fictional AI Labs', 'https://example.com/fictional-ai-labs')
		ON CONFLICT (key) DO UPDATE SET key = EXCLUDED.key
		RETURNING id
	`).Scan(&providerID); err != nil {
		fatal("seed model provider", err)
	}

	var licenceID uuid.UUID
	if err := tx.QueryRow(ctx, `
		INSERT INTO model_licences (key, name, terms_url, allows_commercial_use, allows_redistribution)
		VALUES ('fictional-open-licence', 'Fictional Open Licence', 'https://example.com/licence', true, true)
		ON CONFLICT (key) DO UPDATE SET key = EXCLUDED.key
		RETURNING id
	`).Scan(&licenceID); err != nil {
		fatal("seed model licence", err)
	}

	falconImageDigest := fakeDigest("falcon-inference-image-v1")
	var falconImageID uuid.UUID
	err = tx.QueryRow(ctx, `SELECT id FROM container_images WHERE enterprise_tenant_id = $1 AND digest = $2`, falconTenantID, falconImageDigest).Scan(&falconImageID)
	if err != nil {
		if err := tx.QueryRow(ctx, `
			INSERT INTO container_images (enterprise_tenant_id, registry_host, repository, digest, tag, status, registered_by, approved_by, approved_at)
			VALUES ($1, 'registry.gridkeep-demo.io', 'fictional/rag-inference-api', $2, 'v1', 'approved', $3, $4, now())
			RETURNING id
		`, falconTenantID, falconImageDigest, users[falconOwnerEmail].id, users[falconComplianceEmail].id).Scan(&falconImageID); err != nil {
			fatal("seed Falcon container image", err)
		}
	}

	var falconModelID uuid.UUID
	err = tx.QueryRow(ctx, `SELECT id FROM models WHERE enterprise_tenant_id = $1 AND model_key = $2`, falconTenantID, "fictional-text-embedding").Scan(&falconModelID)
	if err != nil {
		if err := tx.QueryRow(ctx, `
			INSERT INTO models (enterprise_tenant_id, model_key, name, description, provider_id)
			VALUES ($1, 'fictional-text-embedding', 'Fictional Text Embedding Model', 'Fictional demo model -- not a real AI model', $2)
			RETURNING id
		`, falconTenantID, providerID).Scan(&falconModelID); err != nil {
			fatal("seed Falcon model", err)
		}
	}

	var falconModelVersionID uuid.UUID
	err = tx.QueryRow(ctx, `SELECT id FROM model_versions WHERE model_id = $1 AND version = 1`, falconModelID).Scan(&falconModelVersionID)
	if err != nil {
		permittedJSON, _ := json.Marshal([]string{"AE", "SA"})
		workloadTypesJSON, _ := json.Marshal([]string{"embedding_service"})
		if err := tx.QueryRow(ctx, `
			INSERT INTO model_versions (
				model_id, enterprise_tenant_id, version, status, provider_id, licence_id, checksum_sha256,
				permitted_geographies, supported_workload_types, requested_by, approved_by, approved_at
			)
			VALUES ($1, $2, 1, 'approved', $3, $4, $5, $6, $7, $8, $9, now())
			RETURNING id
		`, falconModelID, falconTenantID, providerID, licenceID, strings.TrimPrefix(fakeDigest("falcon-model-weights-v1"), "sha256:"),
			permittedJSON, workloadTypesJSON, users[falconOwnerEmail].id, users[falconComplianceEmail].id).Scan(&falconModelVersionID); err != nil {
			fatal("seed Falcon model version", err)
		}
	}
	if _, err := tx.Exec(ctx, `
		INSERT INTO model_capabilities (enterprise_tenant_id, model_version_id, capability_key, description)
		VALUES ($1, $2, 'semantic-search', 'Fictional semantic search embedding capability')
		ON CONFLICT (model_version_id, capability_key) DO NOTHING
	`, falconTenantID, falconModelVersionID); err != nil {
		fatal("seed Falcon model capability", err)
	}

	var falconWorkloadID uuid.UUID
	err = tx.QueryRow(ctx, `SELECT id FROM workloads WHERE enterprise_tenant_id = $1 AND workload_key = $2`, falconTenantID, "fictional-rag-app").Scan(&falconWorkloadID)
	if err != nil {
		if err := tx.QueryRow(ctx, `
			INSERT INTO workloads (enterprise_tenant_id, workload_key, workload_type, name, description, owner_user_id)
			VALUES ($1, 'fictional-rag-app', 'retrieval_augmented_generation_application', 'Fictional RAG App', 'Fictional demo workload', $2)
			RETURNING id
		`, falconTenantID, users[falconOwnerEmail].id).Scan(&falconWorkloadID); err != nil {
			fatal("seed Falcon workload", err)
		}
	}
	var falconWorkloadVersionID uuid.UUID
	err = tx.QueryRow(ctx, `SELECT id FROM workload_versions WHERE workload_id = $1 AND version = 1`, falconWorkloadID).Scan(&falconWorkloadVersionID)
	if err != nil {
		residencyJSON, _ := json.Marshal(map[string]any{"allowed_countries": []string{"AE"}})
		resourceJSON, _ := json.Marshal(map[string]any{"cpu": "2", "memory_gb": 4})
		if err := tx.QueryRow(ctx, `
			INSERT INTO workload_versions (
				workload_id, enterprise_tenant_id, version, status, container_image_id, model_version_id,
				residency_requirements, resource_requirements, requested_by, approved_by, published_at
			)
			VALUES ($1, $2, 1, 'published', $3, $4, $5, $6, $7, $8, now())
			RETURNING id
		`, falconWorkloadID, falconTenantID, falconImageID, falconModelVersionID,
			residencyJSON, resourceJSON, users[falconOwnerEmail].id, users[falconComplianceEmail].id).Scan(&falconWorkloadVersionID); err != nil {
			fatal("seed Falcon workload version", err)
		}
	}

	if _, err := tx.Exec(ctx, `
		INSERT INTO artefact_uploads (
			enterprise_tenant_id, object_key, bucket, purpose, content_type, content_length,
			checksum_sha256, status, uploaded_by, uploaded_at
		)
		VALUES ($1, $2, 'gridkeep-artefacts', 'model_artefact', 'application/octet-stream', 1048576, $3, 'uploaded', $4, now())
		ON CONFLICT (object_key) DO NOTHING
	`, falconTenantID, "tenants/"+falconTenantID.String()+"/fictional-model-weights-v1",
		strings.TrimPrefix(fakeDigest("falcon-artefact-checksum-v1"), "sha256:"), users[falconOwnerEmail].id); err != nil {
		fatal("seed Falcon artefact upload", err)
	}

	// --- Placement and Capacity Engine (Milestone 5) -------------------------
	// One capacity offer per demo operator -- Gulf Horizon's in the AE region
	// (matching Falcon National Bank's AE-only sovereignty policy above),
	// EuroNorth's in the DE region (deliberately cheaper, to demonstrate that
	// sovereignty gating -- not price -- decides eligibility) -- plus one
	// already-committed reservation for Falcon against the eligible AE offer,
	// inserted directly (like every other already-approved row in this
	// script) rather than through the evaluate/approve-commit HTTP flow, but
	// recording the same requested_by/approved_by dual-control facts a real
	// commit would.
	var gulfOfferID uuid.UUID
	err = tx.QueryRow(ctx, `SELECT id FROM capacity_offers WHERE operator_id = $1 AND cluster_id = $2`, gulfHorizonID, gulfClusterID).Scan(&gulfOfferID)
	if err != nil {
		if err := tx.QueryRow(ctx, `
			INSERT INTO capacity_offers (
				operator_id, cluster_id, region_id, accelerator_type, total_capacity, available_capacity,
				price_per_unit_hour, currency, confidential_computing_available, estimated_kwh_per_unit_hour, created_by
			)
			VALUES ($1, $2, $3, 'nvidia-h100', 16, 16, 3.25, 'USD', true, 0.65, $4)
			RETURNING id
		`, gulfHorizonID, gulfClusterID, meCentral, users[gulfHorizonOwnerEmail].id).Scan(&gulfOfferID); err != nil {
			fatal("seed Gulf Horizon capacity offer", err)
		}
	}

	var euroNorthOfferID uuid.UUID
	err = tx.QueryRow(ctx, `SELECT id FROM capacity_offers WHERE operator_id = $1 AND cluster_id = $2`, euroNorthID, euroNorthClusterID).Scan(&euroNorthOfferID)
	if err != nil {
		if err := tx.QueryRow(ctx, `
			INSERT INTO capacity_offers (
				operator_id, cluster_id, region_id, accelerator_type, total_capacity, available_capacity,
				price_per_unit_hour, currency, confidential_computing_available, estimated_kwh_per_unit_hour, created_by
			)
			VALUES ($1, $2, $3, 'nvidia-h100', 16, 16, 1.80, 'USD', false, 0.55, $4)
			RETURNING id
		`, euroNorthID, euroNorthClusterID, euCentral, users[euroNorthOwnerEmail].id).Scan(&euroNorthOfferID); err != nil {
			fatal("seed EuroNorth capacity offer", err)
		}
	}

	var falconPlacementRequestID uuid.UUID
	err = tx.QueryRow(ctx, `SELECT id FROM placement_requests WHERE workload_version_id = $1`, falconWorkloadVersionID).Scan(&falconPlacementRequestID)
	if err != nil {
		if err := tx.QueryRow(ctx, `
			INSERT INTO placement_requests (enterprise_tenant_id, workload_version_id, quantity, simulate, status, requested_by)
			VALUES ($1, $2, 2, false, 'reserved', $3)
			RETURNING id
		`, falconTenantID, falconWorkloadVersionID, users[falconOwnerEmail].id).Scan(&falconPlacementRequestID); err != nil {
			fatal("seed Falcon placement request", err)
		}

		eligibleExplanation, _ := json.Marshal(map[string]any{
			"sovereignty":            map[string]any{"passed": true, "policies_evaluated": []any{}},
			"security":               map[string]any{"confidential_computing_required": true, "offer_confidential_computing": true, "passed": true},
			"commercial_eligibility": map[string]any{"passed": true, "note": "bilateral agreement gating is out of scope for Milestone 5"},
			"capacity":               map[string]any{"available_capacity": 16, "requested_quantity": 2, "passed": true},
			"runtime_compatibility":  map[string]any{"required_accelerator_type": "", "offer_accelerator_type": "nvidia-h100", "passed": true},
			"cost":                   map[string]any{"price_per_unit_hour": 3.25, "estimated_cost": 6.50},
			"energy":                 map[string]any{"estimated_kwh_per_unit_hour": 0.65, "estimated_energy_kwh": 1.30},
		})
		rejectedExplanation, _ := json.Marshal(map[string]any{
			"sovereignty": map[string]any{"passed": false, "policies_evaluated": []any{
				map[string]any{"policy_id": "fictional", "decision": "deny", "reason_codes": []string{"RESIDENCY_NOT_IN_ALLOWED_COUNTRIES"}},
			}},
		})
		if _, err := tx.Exec(ctx, `
			INSERT INTO placement_evaluations (
				enterprise_tenant_id, placement_request_id, capacity_offer_id, operator_id, region_id,
				accelerator_type, decision, rank, estimated_cost, estimated_energy_kwh, reason_codes, explanation
			) VALUES
				($1, $2, $3, $4, $5, 'nvidia-h100', 'eligible', 1, 6.50, 1.30, '[]'::jsonb, $6),
				($1, $2, $7, $8, $9, 'nvidia-h100', 'rejected', NULL, 3.60, 1.10, '["RESIDENCY_NOT_IN_ALLOWED_COUNTRIES"]'::jsonb, $10)
		`, falconTenantID, falconPlacementRequestID, gulfOfferID, gulfHorizonID, meCentral, eligibleExplanation,
			euroNorthOfferID, euroNorthID, euCentral, rejectedExplanation); err != nil {
			fatal("seed Falcon placement evaluations", err)
		}

		if _, err := tx.Exec(ctx, `
			INSERT INTO capacity_reservations (
				enterprise_tenant_id, operator_id, placement_request_id, capacity_offer_id, quantity,
				price_per_unit_hour, estimated_cost, status, approval_required, requested_by, approved_by,
				expires_at, committed_at
			)
			VALUES ($1, $2, $3, $4, 2, 3.25, 6.50, 'committed', true, $5, $6, now() + interval '15 minutes', now())
		`, falconTenantID, gulfHorizonID, falconPlacementRequestID, gulfOfferID, users[falconOwnerEmail].id, users[falconComplianceEmail].id); err != nil {
			fatal("seed Falcon capacity reservation", err)
		}
		if _, err := tx.Exec(ctx, `
			UPDATE capacity_offers SET available_capacity = available_capacity - 2 WHERE id = $1 AND available_capacity >= 2
		`, gulfOfferID); err != nil {
			fatal("apply Falcon reservation to Gulf Horizon capacity offer", err)
		}
	}

	// --- Network and Edge Services (Milestone 9) -----------------------------
	// One network capability and one network service offer per demo operator
	// (mirroring the capacity offer block above), plus one already-committed
	// network reservation for Falcon -- inserted directly, like every other
	// already-approved row in this script. This milestone's EvaluateAndReserve
	// does not yet gate on sovereignty policy (see docs/project-status.md's
	// Deliberate security decisions for Milestone 9), so both offers are
	// eligible here and ranking is by price alone, EuroNorth's cheaper offer
	// winning -- exactly what a real evaluate call against this seed data
	// would produce. cluster_agent_id is left NULL and provisioning_status
	// stays at its 'pending' default, for the same reason Milestone 6/7/8's
	// seed data does not fabricate a cluster agent identity: a realistic
	// provisioning result requires a real bootstrapped agent, which a
	// schema-migration-style seed script cannot produce. No network health
	// event is seeded either, since none genuinely occurred against this
	// unprovisioned reservation.
	var gulfNetworkCapabilityID uuid.UUID
	err = tx.QueryRow(ctx, `SELECT id FROM network_capabilities WHERE operator_id = $1 AND data_centre_id = $2`, gulfHorizonID, gulfDataCentre).Scan(&gulfNetworkCapabilityID)
	if err != nil {
		if err := tx.QueryRow(ctx, `
			INSERT INTO network_capabilities (operator_id, data_centre_id, capability_type, bandwidth_gbps, estimated_latency_ms)
			VALUES ($1, $2, 'private_5g', 50, 8)
			RETURNING id
		`, gulfHorizonID, gulfDataCentre).Scan(&gulfNetworkCapabilityID); err != nil {
			fatal("seed Gulf Horizon network capability", err)
		}
	}

	var euroNorthNetworkCapabilityID uuid.UUID
	err = tx.QueryRow(ctx, `SELECT id FROM network_capabilities WHERE operator_id = $1 AND data_centre_id = $2`, euroNorthID, euroNorthDataCentre).Scan(&euroNorthNetworkCapabilityID)
	if err != nil {
		if err := tx.QueryRow(ctx, `
			INSERT INTO network_capabilities (operator_id, data_centre_id, capability_type, bandwidth_gbps, estimated_latency_ms)
			VALUES ($1, $2, 'network_slice', 100, 15)
			RETURNING id
		`, euroNorthID, euroNorthDataCentre).Scan(&euroNorthNetworkCapabilityID); err != nil {
			fatal("seed EuroNorth network capability", err)
		}
	}

	var gulfNetworkOfferID uuid.UUID
	err = tx.QueryRow(ctx, `SELECT id FROM network_service_offers WHERE operator_id = $1 AND network_capability_id = $2`, gulfHorizonID, gulfNetworkCapabilityID).Scan(&gulfNetworkOfferID)
	if err != nil {
		if err := tx.QueryRow(ctx, `
			INSERT INTO network_service_offers (
				operator_id, network_capability_id, region_id, service_class, total_bandwidth_gbps,
				available_bandwidth_gbps, max_latency_ms, price_per_unit_hour, currency, created_by
			)
			VALUES ($1, $2, $3, 'private-5g-standard', 50, 50, 8, 2.50, 'USD', $4)
			RETURNING id
		`, gulfHorizonID, gulfNetworkCapabilityID, meCentral, users[gulfHorizonOwnerEmail].id).Scan(&gulfNetworkOfferID); err != nil {
			fatal("seed Gulf Horizon network service offer", err)
		}
	}

	var euroNorthNetworkOfferID uuid.UUID
	err = tx.QueryRow(ctx, `SELECT id FROM network_service_offers WHERE operator_id = $1 AND network_capability_id = $2`, euroNorthID, euroNorthNetworkCapabilityID).Scan(&euroNorthNetworkOfferID)
	if err != nil {
		if err := tx.QueryRow(ctx, `
			INSERT INTO network_service_offers (
				operator_id, network_capability_id, region_id, service_class, total_bandwidth_gbps,
				available_bandwidth_gbps, max_latency_ms, price_per_unit_hour, currency, created_by
			)
			VALUES ($1, $2, $3, 'network-slice-standard', 100, 100, 15, 1.20, 'USD', $4)
			RETURNING id
		`, euroNorthID, euroNorthNetworkCapabilityID, euCentral, users[euroNorthOwnerEmail].id).Scan(&euroNorthNetworkOfferID); err != nil {
			fatal("seed EuroNorth network service offer", err)
		}
	}

	var falconNetworkRequestID uuid.UUID
	err = tx.QueryRow(ctx, `SELECT id FROM network_service_requests WHERE enterprise_tenant_id = $1`, falconTenantID).Scan(&falconNetworkRequestID)
	if err != nil {
		if err := tx.QueryRow(ctx, `
			INSERT INTO network_service_requests (enterprise_tenant_id, required_bandwidth_gbps, max_latency_ms, simulate, status, requested_by)
			VALUES ($1, 5, 20, false, 'reserved', $2)
			RETURNING id
		`, falconTenantID, users[falconOwnerEmail].id).Scan(&falconNetworkRequestID); err != nil {
			fatal("seed Falcon network service request", err)
		}

		eligibleExplanation, _ := json.Marshal(map[string]any{
			"bandwidth":     map[string]any{"available_bandwidth_gbps": 100, "required_bandwidth_gbps": 5, "passed": true},
			"latency":       map[string]any{"required_max_latency_ms": 20, "offer_max_latency_ms": 15, "passed": true},
			"service_class": map[string]any{"required_service_class": nil, "offer_service_class": "network-slice-standard", "passed": true},
			"cost":          map[string]any{"price_per_unit_hour": 1.20, "estimated_cost": 6.00},
		})
		gulfEligibleExplanation, _ := json.Marshal(map[string]any{
			"bandwidth":     map[string]any{"available_bandwidth_gbps": 50, "required_bandwidth_gbps": 5, "passed": true},
			"latency":       map[string]any{"required_max_latency_ms": 20, "offer_max_latency_ms": 8, "passed": true},
			"service_class": map[string]any{"required_service_class": nil, "offer_service_class": "private-5g-standard", "passed": true},
			"cost":          map[string]any{"price_per_unit_hour": 2.50, "estimated_cost": 12.50},
		})
		if _, err := tx.Exec(ctx, `
			INSERT INTO network_service_evaluations (
				enterprise_tenant_id, network_service_request_id, network_service_offer_id, operator_id, region_id,
				service_class, decision, rank, estimated_cost, reason_codes, explanation
			) VALUES
				($1, $2, $3, $4, $5, 'network-slice-standard', 'eligible', 1, 6.00, '[]'::jsonb, $6),
				($1, $2, $7, $8, $9, 'private-5g-standard', 'eligible', 2, 12.50, '[]'::jsonb, $10)
		`, falconTenantID, falconNetworkRequestID, euroNorthNetworkOfferID, euroNorthID, euCentral, eligibleExplanation,
			gulfNetworkOfferID, gulfHorizonID, meCentral, gulfEligibleExplanation); err != nil {
			fatal("seed Falcon network service evaluations", err)
		}

		if _, err := tx.Exec(ctx, `
			INSERT INTO network_reservations (
				enterprise_tenant_id, operator_id, network_service_request_id, network_service_offer_id,
				bandwidth_gbps, price_per_unit_hour, estimated_cost, status, requested_by, committed_at
			)
			VALUES ($1, $2, $3, $4, 5, 1.20, 6.00, 'committed', $5, now())
		`, falconTenantID, euroNorthID, falconNetworkRequestID, euroNorthNetworkOfferID, users[falconOwnerEmail].id); err != nil {
			fatal("seed Falcon network reservation", err)
		}
		if _, err := tx.Exec(ctx, `
			UPDATE network_service_offers SET available_bandwidth_gbps = available_bandwidth_gbps - 5 WHERE id = $1 AND available_bandwidth_gbps >= 5
		`, euroNorthNetworkOfferID); err != nil {
			fatal("apply Falcon reservation to EuroNorth network service offer", err)
		}
	}

	// --- Service Assurance and Observability (Milestone 10) ------------------
	// One SLO and one alert rule per side, each paired with a real evaluation
	// snapshot computed by hand from the exact seed data above (never a
	// fabricated number): Falcon's policy-compliance SLO reflects the 1
	// eligible / 1 rejected placement_evaluations pair seeded above (50%,
	// breached against an 80% target); EuroNorth's network-provisioning SLA
	// reflects its own network_reservations row still sitting at
	// provisioning_status='pending' (0%, since no cluster agent identity is
	// seeded -- see this milestone's Known Limitations), which also drives a
	// genuinely-firing alert and an open incident. All inserted directly
	// rather than through the evaluate/create HTTP flow (like every other
	// already-committed row in this script) but recording the same facts a
	// real call would.
	var falconSLOID uuid.UUID
	err = tx.QueryRow(ctx, `SELECT id FROM slo_definitions WHERE enterprise_tenant_id = $1 AND name = $2`, falconTenantID, "Placement policy compliance").Scan(&falconSLOID)
	if err != nil {
		if err := tx.QueryRow(ctx, `
			INSERT INTO slo_definitions (enterprise_tenant_id, name, metric_source, target_percentage, window_days, created_by)
			VALUES ($1, 'Placement policy compliance', 'policy_compliance_rate', 80, 30, $2)
			RETURNING id
		`, falconTenantID, users[falconOwnerEmail].id).Scan(&falconSLOID); err != nil {
			fatal("seed Falcon SLO", err)
		}
		if _, err := tx.Exec(ctx, `
			INSERT INTO slo_evaluations (slo_definition_id, enterprise_tenant_id, actual_percentage, error_budget_remaining_percentage, status, sample_size, detail)
			VALUES ($1, $2, 50, 30, 'breached', 2, '{"metric_source":"policy_compliance_rate","window_days":30}'::jsonb)
		`, falconSLOID, falconTenantID); err != nil {
			fatal("seed Falcon SLO evaluation", err)
		}
	}

	var euroNorthReservationID uuid.UUID
	if err := tx.QueryRow(ctx, `SELECT id FROM network_reservations WHERE network_service_offer_id = $1`, euroNorthNetworkOfferID).Scan(&euroNorthReservationID); err != nil {
		fatal("resolve EuroNorth network reservation for assurance seed", err)
	}

	var euroNorthSLOID uuid.UUID
	err = tx.QueryRow(ctx, `SELECT id FROM slo_definitions WHERE operator_id = $1 AND name = $2`, euroNorthID, "Network reservation provisioning").Scan(&euroNorthSLOID)
	if err != nil {
		if err := tx.QueryRow(ctx, `
			INSERT INTO slo_definitions (operator_id, name, metric_source, target_percentage, window_days, created_by)
			VALUES ($1, 'Network reservation provisioning', 'network_reservation_provisioning', 95, 1, $2)
			RETURNING id
		`, euroNorthID, users[euroNorthOwnerEmail].id).Scan(&euroNorthSLOID); err != nil {
			fatal("seed EuroNorth SLO", err)
		}
		if _, err := tx.Exec(ctx, `
			INSERT INTO slo_evaluations (slo_definition_id, operator_id, actual_percentage, error_budget_remaining_percentage, status, sample_size, detail)
			VALUES ($1, $2, 0, -5, 'breached', 1, '{"metric_source":"network_reservation_provisioning","window_days":1}'::jsonb)
		`, euroNorthSLOID, euroNorthID); err != nil {
			fatal("seed EuroNorth SLO evaluation", err)
		}
	}

	var euroNorthAlertRuleID uuid.UUID
	err = tx.QueryRow(ctx, `SELECT id FROM alert_rules WHERE operator_id = $1 AND name = $2`, euroNorthID, "Provisioning failure alert").Scan(&euroNorthAlertRuleID)
	if err != nil {
		if err := tx.QueryRow(ctx, `
			INSERT INTO alert_rules (operator_id, name, metric_source, comparison, threshold, severity, created_by)
			VALUES ($1, 'Provisioning failure alert', 'network_reservation_provisioning', 'lt', 50, 'warning', $2)
			RETURNING id
		`, euroNorthID, users[euroNorthOwnerEmail].id).Scan(&euroNorthAlertRuleID); err != nil {
			fatal("seed EuroNorth alert rule", err)
		}
		if _, err := tx.Exec(ctx, `
			INSERT INTO alerts (alert_rule_id, operator_id, value_at_fire, detail)
			VALUES ($1, $2, 0, '{"metric_source":"network_reservation_provisioning","comparison":"lt","threshold":50}'::jsonb)
		`, euroNorthAlertRuleID, euroNorthID); err != nil {
			fatal("seed EuroNorth firing alert", err)
		}
	}

	var euroNorthIncidentID uuid.UUID
	err = tx.QueryRow(ctx, `SELECT id FROM incidents WHERE operator_id = $1 AND title = $2`, euroNorthID, "Network reservation stuck in pending provisioning").Scan(&euroNorthIncidentID)
	if err != nil {
		if err := tx.QueryRow(ctx, `
			INSERT INTO incidents (operator_id, title, description, severity, resource_type, resource_id, opened_by)
			VALUES ($1, 'Network reservation stuck in pending provisioning', 'No active cluster agent is available to provision this reservation in this environment.', 'warning', 'network_reservation', $2, $3)
			RETURNING id
		`, euroNorthID, euroNorthReservationID, users[euroNorthOwnerEmail].id).Scan(&euroNorthIncidentID); err != nil {
			fatal("seed EuroNorth incident", err)
		}
		if _, err := tx.Exec(ctx, `
			INSERT INTO incident_events (incident_id, operator_id, event_type, detail, created_by)
			VALUES ($1, $2, 'opened', '{"severity":"warning"}'::jsonb, $3)
		`, euroNorthIncidentID, euroNorthID, users[euroNorthOwnerEmail].id); err != nil {
			fatal("seed EuroNorth incident event", err)
		}
	}

	if err := tx.Commit(ctx); err != nil {
		fatal("commit seed transaction", err)
	}

	fmt.Println("Seed complete. Fictional demo accounts (password for all:", demoPassword, "):")
	for _, email := range []string{
		platformAdminEmail, falconOwnerEmail, falconComplianceEmail, atlasOwnerEmail, helixOwnerEmail,
		gulfHorizonOwnerEmail, euroNorthOwnerEmail,
	} {
		fmt.Println(" -", email)
	}
}

func fatal(action string, err error) {
	fmt.Fprintf(os.Stderr, "seed failed: %s: %v\n", action, err)
	os.Exit(1)
}
