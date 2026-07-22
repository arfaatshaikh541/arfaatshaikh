package app_test

import (
	"net/url"
	"testing"
	"time"
)

func extractTOTPSecret(t *testing.T, otpauthURI string) string {
	t.Helper()
	u, err := url.Parse(otpauthURI)
	if err != nil {
		t.Fatalf("parse otpauth uri: %v", err)
	}
	secret := u.Query().Get("secret")
	if secret == "" {
		t.Fatalf("no secret found in otpauth uri %s", otpauthURI)
	}
	return secret
}

func timeNow() time.Time {
	return time.Now()
}
