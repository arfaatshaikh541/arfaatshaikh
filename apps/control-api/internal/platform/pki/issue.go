package pki

import (
	"crypto/rand"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"fmt"
	"math/big"
	"time"
)

// SignCSR verifies a CSR's self-signature (proof that the requester
// actually holds the private key matching the public key in the request)
// and, if valid, issues a short-lived leaf certificate for it.
//
// The CSR's own Subject is ignored entirely: callers pass the
// authoritative subjectCN themselves, resolved server-side from a source
// they already trust (e.g. the operator_agent row a validated, single-use
// bootstrap token pointed at) -- never trust an identity claim embedded in
// client-submitted data (see working rule #19).
func (ca *CA) SignCSR(csrPEM []byte, subjectCN string, ttl time.Duration) (certPEM string, serialNumber string, expiresAt time.Time, err error) {
	block, _ := pem.Decode(csrPEM)
	if block == nil || block.Type != "CERTIFICATE REQUEST" {
		return "", "", time.Time{}, fmt.Errorf("not a PEM-encoded certificate request")
	}
	csr, err := x509.ParseCertificateRequest(block.Bytes)
	if err != nil {
		return "", "", time.Time{}, fmt.Errorf("parse CSR: %w", err)
	}
	if err := csr.CheckSignature(); err != nil {
		return "", "", time.Time{}, fmt.Errorf("CSR signature invalid (proof of key possession failed): %w", err)
	}

	serial, err := rand.Int(rand.Reader, new(big.Int).Lsh(big.NewInt(1), 128))
	if err != nil {
		return "", "", time.Time{}, fmt.Errorf("generate serial: %w", err)
	}
	now := time.Now()
	expiresAt = now.Add(ttl)
	template := &x509.Certificate{
		SerialNumber: serial,
		Subject:      pkix.Name{CommonName: subjectCN, Organization: []string{"GRIDKEEP Operator Agent"}},
		NotBefore:    now.Add(-1 * time.Minute),
		NotAfter:     expiresAt,
		KeyUsage:     x509.KeyUsageDigitalSignature,
		ExtKeyUsage:  []x509.ExtKeyUsage{x509.ExtKeyUsageClientAuth},
	}
	der, err := x509.CreateCertificate(rand.Reader, template, ca.cert, csr.PublicKey, ca.key)
	if err != nil {
		return "", "", time.Time{}, fmt.Errorf("create certificate: %w", err)
	}
	certPEM = string(pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: der}))
	return certPEM, serial.String(), expiresAt, nil
}
