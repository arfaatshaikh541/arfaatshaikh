package pki

import (
	"crypto/ecdsa"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/pem"
	"fmt"
)

// SignMessage lets the CA itself sign an outbound message -- Milestone 6's
// signed control-message channel to a cluster agent uses this so an agent
// only ever needs to trust the one CA certificate it already relies on to
// validate its own issued certificate's chain, not a second control-plane
// signing identity. This is the same ECDSA-over-SHA256 construction
// SignMessage (agent.go) uses for agent-to-control-plane signing, mirrored
// for the opposite direction.
func (ca *CA) SignMessage(message []byte) (string, error) {
	digest := sha256.Sum256(message)
	sig, err := ecdsa.SignASN1(rand.Reader, ca.key, digest[:])
	if err != nil {
		return "", fmt.Errorf("sign message: %w", err)
	}
	return base64.StdEncoding.EncodeToString(sig), nil
}

// CertificatePEM returns the CA's own certificate (public information --
// this is what a client verifying a server's TLS certificate would also
// receive) so a cluster agent can fetch it once and verify every
// subsequently received control message's signature against it.
func (ca *CA) CertificatePEM() string {
	return string(pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: ca.cert.Raw}))
}
