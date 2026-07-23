package pki

import (
	"crypto/ecdsa"
	"crypto/sha256"
	"encoding/base64"
	"fmt"
)

// VerifySignature checks that signatureB64 (ASN.1 DER, base64-encoded) is a
// valid ECDSA signature over sha256(message), made with the private key
// corresponding to the public key embedded in certPEM.
//
// It answers exactly one question — "did the holder of this certificate's
// private key sign this exact message?" — and nothing else: it does not
// check the certificate's expiry, revocation status, or which
// operator/agent it is supposed to belong to. Callers (internal/modules/
// agents) hold those facts from agent_certificates and must check them
// separately before trusting a verified signature.
func VerifySignature(certPEM string, message []byte, signatureB64 string) (bool, error) {
	cert, err := parseCertPEM(certPEM)
	if err != nil {
		return false, fmt.Errorf("parse certificate: %w", err)
	}
	pub, ok := cert.PublicKey.(*ecdsa.PublicKey)
	if !ok {
		return false, fmt.Errorf("certificate does not hold an ECDSA public key")
	}
	sig, err := base64.StdEncoding.DecodeString(signatureB64)
	if err != nil {
		return false, fmt.Errorf("decode signature: %w", err)
	}
	digest := sha256.Sum256(message)
	return ecdsa.VerifyASN1(pub, digest[:], sig), nil
}
