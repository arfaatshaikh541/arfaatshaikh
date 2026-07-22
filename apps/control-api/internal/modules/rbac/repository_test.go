package rbac_test

import (
	"context"
	"testing"

	"gridkeep/control-api/internal/modules/rbac"
	"gridkeep/control-api/internal/testutil"
)

// TestRoleGrantableBy is a regression test for an audit finding: invitation
// creation resolved role_key into a role ID with no check on whether the
// inviting user's own role actually holds every permission that target role
// grants. It happened to be safe only because, in today's seed data, the
// sole role permitted to invite in each scope (enterprise_owner /
// enterprise_admin, operator_platform_owner) already holds a superset of
// every other role's permissions in that scope -- so the fix is verified
// directly against the real seeded roles/permissions tables rather than
// relying on that coincidence continuing to hold.
func TestRoleGrantableBy(t *testing.T) {
	store := testutil.NewStore(t)
	ctx := context.Background()

	ownerID, err := rbac.RoleIDByKey(ctx, store.Pool, "enterprise", "enterprise_owner")
	if err != nil {
		t.Fatalf("resolve enterprise_owner: %v", err)
	}
	appOwnerID, err := rbac.RoleIDByKey(ctx, store.Pool, "enterprise", "application_owner")
	if err != nil {
		t.Fatalf("resolve application_owner: %v", err)
	}

	grantable, err := rbac.RoleGrantableBy(ctx, store.Pool, appOwnerID, ownerID)
	if err != nil {
		t.Fatalf("RoleGrantableBy(application_owner, enterprise_owner): %v", err)
	}
	if !grantable {
		t.Fatalf("expected enterprise_owner to be able to grant application_owner (subset of permissions)")
	}

	grantable, err = rbac.RoleGrantableBy(ctx, store.Pool, ownerID, appOwnerID)
	if err != nil {
		t.Fatalf("RoleGrantableBy(enterprise_owner, application_owner): %v", err)
	}
	if grantable {
		t.Fatalf("expected application_owner NOT to be able to grant enterprise_owner (more privileged role)")
	}

	grantable, err = rbac.RoleGrantableBy(ctx, store.Pool, ownerID, ownerID)
	if err != nil {
		t.Fatalf("RoleGrantableBy(enterprise_owner, enterprise_owner): %v", err)
	}
	if !grantable {
		t.Fatalf("expected a role to always be able to grant itself")
	}
}
