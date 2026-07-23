package pki

import (
	"crypto/rand"
	"testing"
	"time"
)

func testEncryptionKey(t *testing.T) []byte {
	t.Helper()
	key := make([]byte, 32)
	if _, err := rand.Read(key); err != nil {
		t.Fatalf("generate test key: %v", err)
	}
	return key
}

func testCA(t *testing.T) *CA {
	t.Helper()
	certPEM, keyPEM, err := generateSelfSigned()
	if err != nil {
		t.Fatalf("generate self-signed CA: %v", err)
	}
	cert, err := parseCertPEM(certPEM)
	if err != nil {
		t.Fatalf("parse CA cert: %v", err)
	}
	key, err := parseECDSAKeyPEM(keyPEM)
	if err != nil {
		t.Fatalf("parse CA key: %v", err)
	}
	return &CA{cert: cert, key: key}
}

func TestEncryptDecryptRoundTrip(t *testing.T) {
	key := testEncryptionKey(t)
	ciphertext, err := encrypt(key, "the CA's private key material")
	if err != nil {
		t.Fatalf("encrypt: %v", err)
	}
	plaintext, err := decrypt(key, ciphertext)
	if err != nil {
		t.Fatalf("decrypt: %v", err)
	}
	if plaintext != "the CA's private key material" {
		t.Fatalf("round trip mismatch: got %q", plaintext)
	}
}

func TestDecrypt_RejectsWrongKey(t *testing.T) {
	key := testEncryptionKey(t)
	wrongKey := testEncryptionKey(t)
	ciphertext, err := encrypt(key, "secret")
	if err != nil {
		t.Fatalf("encrypt: %v", err)
	}
	if _, err := decrypt(wrongKey, ciphertext); err == nil {
		t.Fatalf("expected decrypt with wrong key to fail")
	}
}

func TestSignCSR_IgnoresClientSuppliedSubject(t *testing.T) {
	ca := testCA(t)

	// The agent's CSR claims to be "attacker-supplied-identity" -- the CA
	// must ignore that and use only the subjectCN the caller (control-api,
	// having already resolved the real agent ID from a validated bootstrap
	// token) explicitly passes in.
	_, csrPEM, err := GenerateKeyAndCSR("attacker-supplied-identity")
	if err != nil {
		t.Fatalf("generate CSR: %v", err)
	}

	certPEM, serial, expiresAt, err := ca.SignCSR([]byte(csrPEM), "authoritative-agent-id", time.Hour)
	if err != nil {
		t.Fatalf("sign CSR: %v", err)
	}
	if serial == "" {
		t.Fatalf("expected a non-empty serial number")
	}
	if time.Until(expiresAt) <= 0 || time.Until(expiresAt) > 2*time.Hour {
		t.Fatalf("unexpected expiry: %v", expiresAt)
	}

	cert, err := parseCertPEM(certPEM)
	if err != nil {
		t.Fatalf("parse issued cert: %v", err)
	}
	if cert.Subject.CommonName != "authoritative-agent-id" {
		t.Fatalf("expected issued cert CommonName to be the server-provided value, got %q", cert.Subject.CommonName)
	}
}

func TestSignCSR_RejectsInvalidSignature(t *testing.T) {
	ca := testCA(t)
	tampered := []byte(`-----BEGIN CERTIFICATE REQUEST-----
not a real CSR
-----END CERTIFICATE REQUEST-----`)
	if _, _, _, err := ca.SignCSR(tampered, "agent-id", time.Hour); err == nil {
		t.Fatalf("expected signing a malformed CSR to fail")
	}
}

func TestVerifySignature_RoundTrip(t *testing.T) {
	ca := testCA(t)
	keyPEM, csrPEM, err := GenerateKeyAndCSR("agent-1")
	if err != nil {
		t.Fatalf("generate CSR: %v", err)
	}
	certPEM, _, _, err := ca.SignCSR([]byte(csrPEM), "agent-1", time.Hour)
	if err != nil {
		t.Fatalf("sign CSR: %v", err)
	}

	message := []byte(`{"cluster_id":"11111111-1111-1111-1111-111111111111","node_count":4}`)
	sig, err := SignMessage(keyPEM, message)
	if err != nil {
		t.Fatalf("sign message: %v", err)
	}

	valid, err := VerifySignature(certPEM, message, sig)
	if err != nil {
		t.Fatalf("verify signature: %v", err)
	}
	if !valid {
		t.Fatalf("expected signature to verify against the issued certificate")
	}

	tamperedMessage := []byte(`{"cluster_id":"11111111-1111-1111-1111-111111111111","node_count":40}`)
	valid, err = VerifySignature(certPEM, tamperedMessage, sig)
	if err != nil {
		t.Fatalf("verify tampered message: %v", err)
	}
	if valid {
		t.Fatalf("expected signature over a tampered message to fail verification")
	}
}

func TestVerifySignature_RejectsWrongAgentsSignature(t *testing.T) {
	ca := testCA(t)

	_, csr1, err := GenerateKeyAndCSR("agent-1")
	if err != nil {
		t.Fatalf("generate CSR 1: %v", err)
	}
	cert1, _, _, err := ca.SignCSR([]byte(csr1), "agent-1", time.Hour)
	if err != nil {
		t.Fatalf("sign CSR 1: %v", err)
	}

	key2, csr2, err := GenerateKeyAndCSR("agent-2")
	if err != nil {
		t.Fatalf("generate CSR 2: %v", err)
	}
	if _, _, _, err := ca.SignCSR([]byte(csr2), "agent-2", time.Hour); err != nil {
		t.Fatalf("sign CSR 2: %v", err)
	}

	message := []byte(`{"cluster_id":"22222222-2222-2222-2222-222222222222"}`)
	sigFromAgent2 := mustSign(t, key2, message)

	// Agent 2's signature must not verify against agent 1's certificate.
	valid, err := VerifySignature(cert1, message, sigFromAgent2)
	if err != nil {
		t.Fatalf("verify: %v", err)
	}
	if valid {
		t.Fatalf("expected agent 2's signature to be rejected against agent 1's certificate")
	}
}

func mustSign(t *testing.T, keyPEM string, message []byte) string {
	t.Helper()
	sig, err := SignMessage(keyPEM, message)
	if err != nil {
		t.Fatalf("sign message: %v", err)
	}
	return sig
}
