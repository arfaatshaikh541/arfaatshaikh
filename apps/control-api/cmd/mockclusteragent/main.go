// Command mockclusteragent is Milestone 6's "mock cluster adapter": it
// exercises the real cluster-agent bootstrap, poll, local-enforcement, and
// signed-response APIs end to end, using real cryptography (a real
// generated key pair, a real CSR, real ECDSA signatures in both
// directions) against a real running control-api instance.
//
// It is a MOCK only in the sense the approved architecture asked for:
// there is no real Kubernetes cluster behind it. Delegated operations
// (namespace/quota/network-policy/security-context) are applied to an
// in-memory internal/platform/clusteradapter.Mock, not a real cluster --
// everything else (the crypto, the HTTP calls, the local enforcement
// decision, the database rows control-api writes as a result) is exactly
// what a real cluster agent (a future milestone's daemon running inside an
// operator's cluster) would do. It never fakes a signature check or
// bypasses any verification the server enforces.
//
// Local enforcement performed here, independent of whatever control-api
// already scoped the message to: the plan's signature is verified against
// the platform CA's own certificate (fetched once via the public
// /api/v1/platform-ca/certificate endpoint), and the plan's declared
// cluster_id is checked against the cluster this agent was told (via
// -cluster-id) it is registered for -- a well-built agent does not trust
// transport-level routing alone.
//
// Usage:
//
//	go run ./cmd/mockclusteragent \
//	  -control-api-url http://localhost:8080 \
//	  -cluster-agent-id <cluster_agent id from "register cluster agent"> \
//	  -bootstrap-token <raw token from "register cluster agent"> \
//	  -cluster-id <cluster id this agent is registered for>
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net/http"
	"net/http/cookiejar"
	"os"
	"time"

	"gridkeep/control-api/internal/platform/clusteradapter"
	"gridkeep/control-api/internal/platform/pki"
)

type controlMessage struct {
	ID          string          `json:"id"`
	MessageType string          `json:"message_type"`
	Nonce       string          `json:"nonce"`
	Payload     json.RawMessage `json:"payload"`
	Signature   string          `json:"signature"`
}

type deploymentPlan struct {
	PlanID                string         `json:"plan_id"`
	ClusterID             string         `json:"cluster_id"`
	WorkloadVersionID     *string        `json:"workload_version_id,omitempty"`
	CapacityReservationID *string        `json:"capacity_reservation_id,omitempty"`
	Namespace             string         `json:"namespace"`
	ResourceQuota         map[string]any `json:"resource_quota"`
	NetworkPolicy         map[string]any `json:"network_policy"`
	SecurityContext       map[string]any `json:"security_context"`
}

func main() {
	controlAPIURL := flag.String("control-api-url", "http://localhost:8080", "control-api base URL")
	agentID := flag.String("cluster-agent-id", "", "cluster_agent id returned by 'register cluster agent' (required)")
	bootstrapToken := flag.String("bootstrap-token", "", "raw bootstrap token returned by 'register cluster agent' (required)")
	expectedClusterID := flag.String("cluster-id", "", "cluster id this agent is registered for -- used for local enforcement (required)")
	flag.Parse()

	if *agentID == "" || *bootstrapToken == "" || *expectedClusterID == "" {
		fmt.Fprintln(os.Stderr, "mockclusteragent: -cluster-agent-id, -bootstrap-token, and -cluster-id are all required")
		flag.Usage()
		os.Exit(1)
	}

	jar, err := cookiejar.New(nil)
	if err != nil {
		fatal("create cookie jar", err)
	}
	httpClient := &http.Client{Jar: jar, Timeout: 15 * time.Second}

	csrfToken, err := warmCSRFCookie(httpClient, *controlAPIURL)
	if err != nil {
		fatal("warm CSRF cookie", err)
	}

	fmt.Println("mockclusteragent: generating a real ECDSA P-256 key pair and CSR (private key never leaves this process)...")
	keyPEM, csrPEM, err := pki.GenerateKeyAndCSR(*agentID)
	if err != nil {
		fatal("generate key and CSR", err)
	}

	fmt.Println("mockclusteragent: submitting CSR to POST /api/v1/cluster-agent-bootstrap...")
	certPEM, err := bootstrap(httpClient, *controlAPIURL, csrfToken, *bootstrapToken, csrPEM)
	if err != nil {
		fatal("bootstrap", err)
	}
	fmt.Println("mockclusteragent: received a signed certificate from the GRIDKEEP local development CA.")

	fmt.Println("mockclusteragent: fetching the platform CA's own certificate to verify inbound control messages...")
	caCertPEM, err := fetchCACertificate(httpClient, *controlAPIURL)
	if err != nil {
		fatal("fetch CA certificate", err)
	}

	fmt.Println("mockclusteragent: polling for pending control messages...")
	messages, err := pollPendingMessages(httpClient, *controlAPIURL, *agentID, keyPEM)
	if err != nil {
		fatal("poll pending control messages", err)
	}
	if len(messages) == 0 {
		fmt.Println("mockclusteragent: no pending messages. Nothing to validate. Done.")
		fmt.Println("Issued certificate (safe to print -- it is public key material, not a secret):")
		fmt.Println(certPEM)
		return
	}

	adapter := clusteradapter.NewMock()
	for _, msg := range messages {
		fmt.Printf("mockclusteragent: evaluating control message %s (%s)...\n", msg.ID, msg.MessageType)
		decision, reasonCodes := evaluatePlan(caCertPEM, msg, *expectedClusterID, adapter)
		fmt.Printf("mockclusteragent: local enforcement decision: %s %v\n", decision, reasonCodes)

		if err := respond(httpClient, *controlAPIURL, keyPEM, *agentID, msg.ID, decision, reasonCodes); err != nil {
			fatal("respond to control message", err)
		}
		fmt.Println("mockclusteragent: signed response submitted and accepted.")
	}

	fmt.Println("mockclusteragent: done.")
}

// evaluatePlan is the local-enforcement step: independent signature
// verification against the CA's own certificate, then an independent
// content check (the plan must declare the cluster this agent is actually
// registered for) -- neither check trusts that control-api's own routing
// already got this right. Only on both passing does it exercise the
// delegated, policy-restricted cluster-adapter operations.
func evaluatePlan(caCertPEM string, msg controlMessage, expectedClusterID string, adapter *clusteradapter.Mock) (decision string, reasonCodes []string) {
	valid, err := pki.VerifySignature(caCertPEM, msg.Payload, msg.Signature)
	if err != nil || !valid {
		return "deny", []string{"INVALID_SIGNATURE"}
	}

	var plan deploymentPlan
	if err := json.Unmarshal(msg.Payload, &plan); err != nil {
		return "deny", []string{"MALFORMED_PLAN"}
	}
	if plan.ClusterID != expectedClusterID {
		return "deny", []string{"CLUSTER_ID_MISMATCH"}
	}

	ctx := context.Background()
	if err := adapter.CreateNamespace(ctx, plan.Namespace); err != nil {
		return "deny", []string{"NAMESPACE_CREATION_FAILED"}
	}
	if err := adapter.ApplyResourceQuota(ctx, plan.Namespace, plan.ResourceQuota); err != nil {
		return "deny", []string{"RESOURCE_QUOTA_FAILED"}
	}
	if err := adapter.ApplyNetworkPolicy(ctx, plan.Namespace, plan.NetworkPolicy); err != nil {
		return "deny", []string{"NETWORK_POLICY_FAILED"}
	}
	if err := adapter.ApplySecurityContext(ctx, plan.Namespace, plan.SecurityContext); err != nil {
		return "deny", []string{"SECURITY_CONTEXT_FAILED"}
	}
	return "allow", []string{}
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
	req, err := http.NewRequest(http.MethodPost, baseURL+"/api/v1/cluster-agent-bootstrap", bytes.NewReader(body))
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

func fetchCACertificate(c *http.Client, baseURL string) (string, error) {
	resp, err := c.Get(baseURL + "/api/v1/platform-ca/certificate")
	if err != nil {
		return "", err
	}
	defer func() { _ = resp.Body.Close() }()
	respBody, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("fetch CA certificate failed: HTTP %d: %s", resp.StatusCode, string(respBody))
	}
	var parsed struct {
		CertificatePEM string `json:"certificate_pem"`
	}
	if err := json.Unmarshal(respBody, &parsed); err != nil {
		return "", fmt.Errorf("parse CA certificate response: %w", err)
	}
	return parsed.CertificatePEM, nil
}

// pollPendingMessages proves identity for this read-only, idempotent
// request by signing a canonical challenge string built from the agent id,
// a fresh nonce, and the current time -- the same private key and
// verification function capacity-snapshot submission and control-message
// responses use, just applied to a constructed string rather than a
// request body, since a GET has no body to sign over.
func pollPendingMessages(c *http.Client, baseURL, agentID, keyPEM string) ([]controlMessage, error) {
	nonce := fmt.Sprintf("poll-%d", time.Now().UnixNano())
	signedAt := time.Now().UTC().Format(time.RFC3339)
	challenge := fmt.Sprintf("poll:%s:%s:%s", agentID, nonce, signedAt)
	signature, err := pki.SignMessage(keyPEM, []byte(challenge))
	if err != nil {
		return nil, fmt.Errorf("sign poll challenge: %w", err)
	}

	req, err := http.NewRequest(http.MethodGet, baseURL+"/api/v1/cluster-agents/"+agentID+"/control-messages/pending", nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("X-Agent-Nonce", nonce)
	req.Header.Set("X-Agent-Signed-At", signedAt)
	req.Header.Set("X-Agent-Signature", signature)

	resp, err := c.Do(req)
	if err != nil {
		return nil, err
	}
	defer func() { _ = resp.Body.Close() }()
	respBody, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("poll failed: HTTP %d: %s", resp.StatusCode, string(respBody))
	}
	var messages []controlMessage
	if err := json.Unmarshal(respBody, &messages); err != nil {
		return nil, fmt.Errorf("parse pending messages: %w", err)
	}
	return messages, nil
}

// respond signs its own JSON body (nonce + signed_at included, so they are
// covered by the same signature -- the exact discipline
// SubmitCapacitySnapshot on the control-api side already uses) and submits
// the agent's independently-reached decision.
func respond(c *http.Client, baseURL, keyPEM, agentID, messageID, decision string, reasonCodes []string) error {
	body, err := json.Marshal(map[string]any{
		"decision":     decision,
		"reason_codes": reasonCodes,
		"nonce":        fmt.Sprintf("respond-%d", time.Now().UnixNano()),
		"signed_at":    time.Now().UTC().Format(time.RFC3339),
	})
	if err != nil {
		return err
	}
	signature, err := pki.SignMessage(keyPEM, body)
	if err != nil {
		return fmt.Errorf("sign response: %w", err)
	}

	req, err := http.NewRequest(http.MethodPost, baseURL+"/api/v1/cluster-agents/"+agentID+"/control-messages/"+messageID+"/respond", bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Agent-Signature", signature)

	resp, err := c.Do(req)
	if err != nil {
		return err
	}
	defer func() { _ = resp.Body.Close() }()
	respBody, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusCreated {
		return fmt.Errorf("respond failed: HTTP %d: %s", resp.StatusCode, string(respBody))
	}
	return nil
}

func fatal(step string, err error) {
	fmt.Fprintf(os.Stderr, "mockclusteragent: %s: %v\n", step, err)
	os.Exit(1)
}
