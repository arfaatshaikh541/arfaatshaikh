package app_test

import (
	"net/http"
	"testing"

	"gridkeep/control-api/internal/testutil"
)

// TestEnterpriseInvitationAcceptHappyPath covers the invitation lifecycle
// end to end -- creation by an owner, delivery via (fake) email, and
// acceptance by the correctly-invited, authenticated user -- which had no
// automated test coverage at all before this audit.
func TestEnterpriseInvitationAcceptHappyPath(t *testing.T) {
	srv, smtp, _ := testServer(t)
	ownerEmail := "tenant-owner@example.com"
	owner := registerVerifyAndLogin(t, httpTestServer{URL: srv.URL}, smtp, ownerEmail)

	resp, body := owner.post("/api/v1/enterprises", map[string]string{
		"legal_name": "Acme Corp", "country": "US",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create tenant: expected 201, got %d: %v", resp.StatusCode, body)
	}
	tenantID := str(t, body, "id")

	inviteeEmail := "invitee@example.com"
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/invitations", map[string]string{
		"email": inviteeEmail, "role_key": "application_owner",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create invitation: expected 201, got %d: %v", resp.StatusCode, body)
	}

	msg, ok := smtp.LastMessageContaining(inviteeEmail)
	if !ok {
		t.Fatalf("no invitation email captured for %s", inviteeEmail)
	}
	token, err := testutil.ExtractToken(msg)
	if err != nil {
		t.Fatalf("extract invitation token: %v", err)
	}

	invitee := registerVerifyAndLogin(t, httpTestServer{URL: srv.URL}, smtp, inviteeEmail)
	resp, body = invitee.post("/api/v1/invitations/accept", map[string]string{"token": token})
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("accept invitation: expected 200, got %d: %v", resp.StatusCode, body)
	}
	if got := str(t, body, "enterprise_tenant_id"); got != tenantID {
		t.Fatalf("accept invitation: expected tenant %s, got %s", tenantID, got)
	}
}

// TestEnterpriseInvitationRejectsWrongAccepter is a regression test for an
// audit finding: AcceptInvitation created a membership for whichever
// authenticated user held a valid invitation token, without checking that
// the token's target email matched their own account -- so a token
// intercepted or guessed by anyone with any verified GRIDKEEP account (not
// just the intended recipient) could be redeemed to join the tenant.
func TestEnterpriseInvitationRejectsWrongAccepter(t *testing.T) {
	srv, smtp, _ := testServer(t)
	ownerEmail := "tenant-owner-2@example.com"
	owner := registerVerifyAndLogin(t, httpTestServer{URL: srv.URL}, smtp, ownerEmail)

	resp, body := owner.post("/api/v1/enterprises", map[string]string{
		"legal_name": "Beta Corp", "country": "US",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create tenant: expected 201, got %d: %v", resp.StatusCode, body)
	}
	tenantID := str(t, body, "id")

	inviteeEmail := "real-invitee@example.com"
	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/invitations", map[string]string{
		"email": inviteeEmail, "role_key": "application_owner",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create invitation: expected 201, got %d: %v", resp.StatusCode, body)
	}

	msg, ok := smtp.LastMessageContaining(inviteeEmail)
	if !ok {
		t.Fatalf("no invitation email captured for %s", inviteeEmail)
	}
	token, err := testutil.ExtractToken(msg)
	if err != nil {
		t.Fatalf("extract invitation token: %v", err)
	}

	attacker := registerVerifyAndLogin(t, httpTestServer{URL: srv.URL}, smtp, "attacker@example.com")
	resp, body = attacker.post("/api/v1/invitations/accept", map[string]string{"token": token})
	if resp.StatusCode != http.StatusForbidden {
		t.Fatalf("accept invitation as wrong user: expected 403, got %d: %v", resp.StatusCode, body)
	}
}

// TestEnterpriseInvitationRejectsUnknownRole proves an inviter cannot smuggle
// in an arbitrary, non-existent role key.
func TestEnterpriseInvitationRejectsUnknownRole(t *testing.T) {
	srv, smtp, _ := testServer(t)
	ownerEmail := "tenant-owner-3@example.com"
	owner := registerVerifyAndLogin(t, httpTestServer{URL: srv.URL}, smtp, ownerEmail)

	resp, body := owner.post("/api/v1/enterprises", map[string]string{
		"legal_name": "Gamma Corp", "country": "US",
	})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("create tenant: expected 201, got %d: %v", resp.StatusCode, body)
	}
	tenantID := str(t, body, "id")

	resp, body = owner.post("/api/v1/enterprises/"+tenantID+"/invitations", map[string]string{
		"email": "someone@example.com", "role_key": "does_not_exist",
	})
	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("create invitation with unknown role: expected 400, got %d: %v", resp.StatusCode, body)
	}
}
