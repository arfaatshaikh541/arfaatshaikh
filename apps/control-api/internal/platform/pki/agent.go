package pki

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/sha256"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/base64"
	"encoding/pem"
	"fmt"
)

// The functions in this file are what an operator-agent identity holder
// does, not what the CA does: generate its own key pair, prove possession
// of it via a CSR, and sign messages with it afterward. They are exported
// from this package (rather than living only in cmd/mockconnector) so a
// real operator-agent binary, when Milestone 6 builds one, can reuse the
// exact same crypto rather than reimplementing it -- Milestone 2's mock
// connector is the only current caller.

// GenerateKeyAndCSR creates a fresh ECDSA P-256 key pair and a
// self-signed-proof CSR for it. The returned CSR's Subject is informational
// only — the CA that eventually signs it (see CA.SignCSR) ignores it and
// sets the certificate's real Subject from a source it trusts itself.
func GenerateKeyAndCSR(subjectHint string) (keyPEM, csrPEM string, err error) {
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		return "", "", fmt.Errorf("generate key: %w", err)
	}
	template := &x509.CertificateRequest{
		Subject: pkix.Name{CommonName: subjectHint},
	}
	der, err := x509.CreateCertificateRequest(rand.Reader, template, key)
	if err != nil {
		return "", "", fmt.Errorf("create CSR: %w", err)
	}
	csrPEM = string(pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE REQUEST", Bytes: der}))
	return encodeECDSAKeyPEM(key), csrPEM, nil
}

// SignMessage produces the ASN.1 DER, base64-encoded ECDSA signature over
// sha256(message) that VerifySignature checks on the receiving end.
func SignMessage(keyPEM string, message []byte) (string, error) {
	key, err := parseECDSAKeyPEM(keyPEM)
	if err != nil {
		return "", fmt.Errorf("parse private key: %w", err)
	}
	digest := sha256.Sum256(message)
	sig, err := ecdsa.SignASN1(rand.Reader, key, digest[:])
	if err != nil {
		return "", fmt.Errorf("sign: %w", err)
	}
	return base64.StdEncoding.EncodeToString(sig), nil
}
