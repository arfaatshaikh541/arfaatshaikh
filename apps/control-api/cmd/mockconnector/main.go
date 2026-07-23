// Command mockconnector is the Milestone 2 "mock operator connector": it
// exercises the real operator-agent bootstrap and signed capacity-snapshot
// submission APIs end to end, using real cryptography (a real generated key
// pair, a real CSR, a real ECDSA signature) against a real running
// control-api instance and a real Postgres database.
//
// It is a MOCK only in the sense the approved architecture asked for: there
// is no real GPU cluster or Kubernetes control plane behind it. The
// capacity-snapshot payload it submits is fabricated, clearly labeled
// below, and everything else -- the crypto, the HTTP calls, the database
// rows it causes to be written -- is exactly what a real operator-agent
// (built in a later milestone) would do. It never fakes persistence or
// bypasses any authorization/signature check the server enforces.
//
// Usage:
//
//	go run ./cmd/mockconnector \
//	  -control-api-url http://localhost:8080 \
//	  -agent-id <operator_agent id from "register agent"> \
//	  -bootstrap-token <raw token from "register agent"> \
//	  -cluster-id <cluster id the snapshot should be attributed to>
package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net/http"
	"net/http/cookiejar"
	"os"
	"time"

	"gridkeep/control-api/internal/platform/pki"
)

func main() {
	controlAPIURL := flag.String("control-api-url", "http://localhost:8080", "control-api base URL")
	agentID := flag.String("agent-id", "", "operator_agent id returned by 'register agent' (required)")
	bootstrapToken := flag.String("bootstrap-token", "", "raw bootstrap token returned by 'register agent' (required)")
	clusterID := flag.String("cluster-id", "", "cluster id the fabricated capacity snapshot should be attributed to (required)")
	flag.Parse()

	if *agentID == "" || *bootstrapToken == "" || *clusterID == "" {
		fmt.Fprintln(os.Stderr, "mockconnector: -agent-id, -bootstrap-token, and -cluster-id are all required")
		flag.Usage()
		os.Exit(1)
	}

	jar, err := cookiejar.New(nil)
	if err != nil {
		fatal("create cookie jar", err)
	}
	httpClient := &http.Client{Jar: jar, Timeout: 15 * time.Second}

	// Warm the CSRF cookie the same way the web frontend does. The two
	// machine-facing routes below are exempt from the CSRF check itself
	// (see httpserver.CSRFProtect's exemptPrefixes), but warming here keeps
	// this client's request pattern uniform and makes it trivially reusable
	// against a route that isn't exempt in the future.
	csrfToken, err := warmCSRFCookie(httpClient, *controlAPIURL)
	if err != nil {
		fatal("warm CSRF cookie", err)
	}

	fmt.Println("mockconnector: generating a real ECDSA P-256 key pair and CSR (private key never leaves this process)...")
	keyPEM, csrPEM, err := pki.GenerateKeyAndCSR(*agentID)
	if err != nil {
		fatal("generate key and CSR", err)
	}

	fmt.Println("mockconnector: submitting CSR to POST /api/v1/agent-bootstrap...")
	certPEM, err := bootstrap(httpClient, *controlAPIURL, csrfToken, *bootstrapToken, csrPEM)
	if err != nil {
		fatal("bootstrap", err)
	}
	fmt.Println("mockconnector: received a signed certificate from the GRIDKEEP local development CA.")

	// FICTIONAL, fabricated capacity facts -- there is no real cluster
	// behind this. A real operator-agent (Milestone 6) would collect these
	// from the actual Kubernetes API / node inventory.
	payload := map[string]any{
		"is_fictional_demo_data": true,
		"node_count":             8,
		"accelerator_type":       "NVIDIA H100",
		"accelerator_count":      64,
		"cpu_cores_available":    2048,
		"memory_gb_available":    16384,
	}
	snapshotBody, err := json.Marshal(map[string]any{
		"cluster_id":   *clusterID,
		"collected_at": time.Now().UTC().Format(time.RFC3339),
		"payload":      payload,
	})
	if err != nil {
		fatal("marshal capacity snapshot", err)
	}

	fmt.Println("mockconnector: signing the capacity snapshot with the issued certificate's private key...")
	signature, err := pki.SignMessage(keyPEM, snapshotBody)
	if err != nil {
		fatal("sign capacity snapshot", err)
	}

	fmt.Println("mockconnector: submitting signed capacity snapshot to POST /api/v1/agents/{agentID}/capacity-snapshots...")
	if err := submitCapacitySnapshot(httpClient, *controlAPIURL, csrfToken, *agentID, snapshotBody, signature); err != nil {
		fatal("submit capacity snapshot", err)
	}

	fmt.Println("mockconnector: done. Certificate issued and one signed capacity snapshot accepted.")
	fmt.Println("Issued certificate (safe to print -- it is public key material, not a secret):")
	fmt.Println(certPEM)
}

func warmCSRFCookie(c *http.Client, baseURL string) (string, error) {
	resp, err := c.Get(baseURL + "/healthz")
	if err != nil {
		return "", err
	}
	defer func() { _ = resp.Body.Close() }()
	for _, cookie := range resp.Cookies() {
		if cookie.Name == "gridkeep_csrf" {
			return cookie.Value, nil
		}
	}
	return "", nil
}

func bootstrap(c *http.Client, baseURL, csrfToken, bootstrapToken, csrPEM string) (string, error) {
	body, err := json.Marshal(map[string]string{"bootstrap_token": bootstrapToken, "csr_pem": csrPEM})
	if err != nil {
		return "", err
	}
	req, err := http.NewRequest(http.MethodPost, baseURL+"/api/v1/agent-bootstrap", bytes.NewReader(body))
	if err != nil {
		return "", err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-CSRF-Token", csrfToken)

	resp, err := c.Do(req)
	if err != nil {
		return "", err
	}
	defer func() { _ = resp.Body.Close() }()
	respBody, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusCreated {
		return "", fmt.Errorf("bootstrap failed: HTTP %d: %s", resp.StatusCode, string(respBody))
	}
	var parsed struct {
		CertificatePEM string `json:"certificate_pem"`
	}
	if err := json.Unmarshal(respBody, &parsed); err != nil {
		return "", fmt.Errorf("parse bootstrap response: %w", err)
	}
	return parsed.CertificatePEM, nil
}

func submitCapacitySnapshot(c *http.Client, baseURL, csrfToken, agentID string, snapshotBody []byte, signature string) error {
	req, err := http.NewRequest(http.MethodPost, baseURL+"/api/v1/agents/"+agentID+"/capacity-snapshots", bytes.NewReader(snapshotBody))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-CSRF-Token", csrfToken)
	req.Header.Set("X-Agent-Signature", signature)

	resp, err := c.Do(req)
	if err != nil {
		return err
	}
	defer func() { _ = resp.Body.Close() }()
	respBody, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusCreated {
		return fmt.Errorf("submit failed: HTTP %d: %s", resp.StatusCode, string(respBody))
	}
	return nil
}

func fatal(step string, err error) {
	fmt.Fprintf(os.Stderr, "mockconnector: %s: %v\n", step, err)
	os.Exit(1)
}
