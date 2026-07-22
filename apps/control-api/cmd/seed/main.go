// Command seed populates the local development database with clearly
// labeled FICTIONAL demo data: operators, enterprise tenants, users, and
// memberships. Every seeded operator/tenant row sets
// is_fictional_demo_data = true, and the UI displays a "Fictional demo
// data" badge wherever that flag is set. This must never be run against a
// production database -- it is gated by CONTROL_API_ENV below.
package main

import (
	"context"
	"fmt"
	"os"

	"github.com/google/uuid"

	dbpkg "gridkeep/control-api/internal/platform/db"
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
	atlasOwnerEmail := "owner@atlas-gov.demo.gridkeep.io"
	helixOwnerEmail := "owner@helix-manufacturing.demo.gridkeep.io"
	gulfHorizonOwnerEmail := "owner@gulf-horizon-telecom.demo.gridkeep.io"
	euroNorthOwnerEmail := "owner@euronorth-communications.demo.gridkeep.io"

	for _, email := range []string{
		platformAdminEmail, falconOwnerEmail, atlasOwnerEmail, helixOwnerEmail,
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

	tenantID("Falcon National Bank Demo", "Falcon National Bank Demo", "AE", falconOwnerEmail, "enterprise_sovereign")
	tenantID("Atlas Government Services Demo", "Atlas Government Services Demo", "AE", atlasOwnerEmail, "enterprise_sovereign")
	tenantID("Helix Manufacturing Demo", "Helix Manufacturing Demo", "DE", helixOwnerEmail, "enterprise_growth")

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

	operatorID("Gulf Horizon Telecom Demo", "Gulf Horizon Telecom Demo", "AE", gulfHorizonOwnerEmail, "operator_premium")
	operatorID("EuroNorth Communications Demo", "EuroNorth Communications Demo", "DE", euroNorthOwnerEmail, "operator_standard")

	if err := tx.Commit(ctx); err != nil {
		fatal("commit seed transaction", err)
	}

	fmt.Println("Seed complete. Fictional demo accounts (password for all:", demoPassword, "):")
	for _, email := range []string{
		platformAdminEmail, falconOwnerEmail, atlasOwnerEmail, helixOwnerEmail,
		gulfHorizonOwnerEmail, euroNorthOwnerEmail,
	} {
		fmt.Println(" -", email)
	}
}

func fatal(action string, err error) {
	fmt.Fprintf(os.Stderr, "seed failed: %s: %v\n", action, err)
	os.Exit(1)
}
