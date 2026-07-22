package security

import (
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/base64"
	"encoding/hex"
	"fmt"
)

// GenerateOpaqueToken returns a URL-safe random token suitable for session
// IDs, email verification links, and password reset links. The raw token is
// only ever handed to the client (session cookie, emailed link); the
// database stores only its SHA-256 hash so a database read alone can never
// reconstruct a usable credential.
func GenerateOpaqueToken(numBytes int) (raw string, hash string, err error) {
	buf := make([]byte, numBytes)
	if _, err := rand.Read(buf); err != nil {
		return "", "", fmt.Errorf("generate random token: %w", err)
	}
	raw = base64.RawURLEncoding.EncodeToString(buf)
	hash = HashToken(raw)
	return raw, hash, nil
}

func HashToken(raw string) string {
	sum := sha256.Sum256([]byte(raw))
	return hex.EncodeToString(sum[:])
}

func ConstantTimeEquals(a, b string) bool {
	return subtle.ConstantTimeCompare([]byte(a), []byte(b)) == 1
}
