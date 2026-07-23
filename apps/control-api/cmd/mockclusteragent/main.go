// Command mockclusteragent is Milestone 6's "mock cluster adapter", extended
// in Milestone 7 to also execute deployment_command messages: it exercises
// the real cluster-agent bootstrap, poll, local-enforcement, and
// signed-response/signed-result APIs end to end, using real cryptography (a
// real generated key pair, a real CSR, real ECDSA signatures in both
// directions) against a real running control-api instance.
//
// It is a MOCK only in the sense the approved architecture asked for:
// there is no real Kubernetes cluster behind it. Delegated operations
// (namespace/quota/network-policy/security-context, and now deploy/scale/
// pause/resume/rollback/terminate) are applied to an in-memory
// internal/platform/clusteradapter.Mock, not a real cluster -- everything
// else (the crypto, the HTTP calls, the local enforcement decision, the
// database rows control-api writes as a result) is exactly what a real
// cluster agent (a future milestone's daemon running inside an operator's
// cluster) would do. It never fakes a signature check or bypasses any
// verification the server enforces.
//
// Local enforcement performed here, independent of whatever control-api
// already scoped the message to: every message's signature is verified
// against the platform CA's own certificate (fetched once via the public
// /api/v1/platform-ca/certificate endpoint) before any of its content is
// trusted; a deployment_plan_validate message's declared cluster_id is
// additionally checked against the cluster this agent was told (via
// -cluster-id) it is registered for -- a well-built agent does not trust
// transport-level routing alone. Before executing a "deploy" command, the
// agent fetches this deployment's decrypted secret values through the
// agent-facing, certificate-authenticated secrets endpoint -- this process
// never receives a secret value any other way (control-api's own session-
// authenticated responses never carry one). Milestone 8 adds: if that
// fetch is rejected because the deployment requires confidential computing
// and has no fresh, passing attestation result, this agent runs the
// remote-attestation protocol itself (request a server-issued challenge,
// produce a fixed, clearly-labelled mock hardware report, submit it for
// verification) before retrying the fetch -- see fetchSecretsWithAttestationRetry.
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

// deploymentCommand mirrors control-api's internal (unexported)
// deploymentCommandPayload -- Milestone 7's generic to_agent message shape
// for deploy/scale/pause/resume/rollback/terminate, discriminated by
// Action.
type deploymentCommand struct {
	Action       string         `json:"action"`
	DeploymentID string         `json:"deployment_id"`
	Namespace    string         `json:"namespace,omitempty"`
	Manifest     map[string]any `json:"manifest,omitempty"`
	ReplicaCount int            `json:"replica_count,omitempty"`
	PlanVersion  int            `json:"plan_version,omitempty"`
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

		switch msg.MessageType {
		case "deployment_command":
			action, success, detail := executeDeploymentCommand(httpClient, *controlAPIURL, keyPEM, *agentID, caCertPEM, msg, adapter)
			fmt.Printf("mockclusteragent: executed %q, success=%v: %s\n", action, success, detail)
			if err := reportCommandResult(httpClient, *controlAPIURL, keyPEM, *agentID, msg.ID, action, success, detail); err != nil {
				fatal("report command result", err)
			}
			fmt.Println("mockclusteragent: signed command result submitted and accepted.")
		default:
			decision, reasonCodes := evaluatePlan(caCertPEM, msg, *expectedClusterID, adapter)
			fmt.Printf("mockclusteragent: local enforcement decision: %s %v\n", decision, reasonCodes)
			if err := respond(httpClient, *controlAPIURL, keyPEM, *agentID, msg.ID, decision, reasonCodes); err != nil {
				fatal("respond to control message", err)
			}
			fmt.Println("mockclusteragent: signed response submitted and accepted.")
		}
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

// executeDeploymentCommand is deployment_command's local-enforcement step,
// exactly mirroring evaluatePlan's discipline: verify the signature against
// the CA's own certificate before trusting any content, then act only
// through internal/platform/clusteradapter's narrow method set. Before a
// "deploy", it fetches this deployment's decrypted secrets over the
// certificate-authenticated agent-secrets endpoint and folds them into the
// manifest handed to the adapter -- the one point in this whole flow where
// a secret value exists in memory, and only in this process's, never
// control-api's own session-authenticated responses.
func executeDeploymentCommand(c *http.Client, baseURL, keyPEM, agentID, caCertPEM string, msg controlMessage, adapter *clusteradapter.Mock) (action string, success bool, detail string) {
	valid, err := pki.VerifySignature(caCertPEM, msg.Payload, msg.Signature)
	if err != nil || !valid {
		return "unknown", false, "invalid signature"
	}
	var cmd deploymentCommand
	if err := json.Unmarshal(msg.Payload, &cmd); err != nil {
		return "unknown", false, "malformed command payload"
	}

	ctx := context.Background()
	switch cmd.Action {
	case "deploy", "rollback":
		if err := adapter.CreateNamespace(ctx, cmd.Namespace); err != nil {
			return cmd.Action, false, fmt.Sprintf("create namespace: %v", err)
		}
		manifest := cmd.Manifest
		if manifest == nil {
			manifest = map[string]any{}
		}
		secrets, err := fetchSecretsWithAttestationRetry(c, baseURL, keyPEM, agentID, cmd.DeploymentID)
		if err != nil {
			return cmd.Action, false, fmt.Sprintf("fetch secrets: %v", err)
		}
		manifest["resolved_secret_keys"] = secretKeys(secrets)
		if cmd.Action == "deploy" {
			if err := adapter.DeployWorkload(ctx, cmd.Namespace, cmd.DeploymentID, manifest, cmd.ReplicaCount); err != nil {
				return cmd.Action, false, fmt.Sprintf("deploy workload: %v", err)
			}
		} else {
			if err := adapter.RollbackWorkload(ctx, cmd.DeploymentID, manifest); err != nil {
				return cmd.Action, false, fmt.Sprintf("rollback workload: %v", err)
			}
		}
		return cmd.Action, true, fmt.Sprintf("%s applied with %d resolved secret(s)", cmd.Action, len(secrets))
	case "scale":
		if err := adapter.ScaleWorkload(ctx, cmd.DeploymentID, cmd.ReplicaCount); err != nil {
			return cmd.Action, false, fmt.Sprintf("scale workload: %v", err)
		}
		return cmd.Action, true, fmt.Sprintf("scaled to %d replicas", cmd.ReplicaCount)
	case "pause":
		if err := adapter.PauseWorkload(ctx, cmd.DeploymentID); err != nil {
			return cmd.Action, false, fmt.Sprintf("pause workload: %v", err)
		}
		return cmd.Action, true, "paused"
	case "resume":
		if err := adapter.ResumeWorkload(ctx, cmd.DeploymentID); err != nil {
			return cmd.Action, false, fmt.Sprintf("resume workload: %v", err)
		}
		return cmd.Action, true, "resumed"
	case "terminate":
		if err := adapter.TerminateWorkload(ctx, cmd.DeploymentID); err != nil {
			return cmd.Action, false, fmt.Sprintf("terminate workload: %v", err)
		}
		return cmd.Action, true, "terminated"
	default:
		return cmd.Action, false, "unknown action"
	}
}

func secretKeys(secrets map[string]string) []string {
	keys := make([]string, 0, len(secrets))
	for k := range secrets {
		keys = append(keys, k)
	}
	return keys
}

// fetchAgentSecrets proves identity the same way pollPendingMessages does --
// a signature over a canonical challenge string built from this agent's id,
// the target deployment's id, a fresh nonce, and the current time -- and
// returns the decrypted secret values control-api will only ever hand to
// the one cluster agent actually assigned to that deployment. The status
// code is returned alongside the error so a caller can distinguish "this
// deployment requires a fresh attestation" (409) from any other failure
// without string-matching the error message.
func fetchAgentSecrets(c *http.Client, baseURL, keyPEM, agentID, deploymentID string) (secrets map[string]string, statusCode int, err error) {
	nonce := fmt.Sprintf("secrets-%d", time.Now().UnixNano())
	signedAt := time.Now().UTC().Format(time.RFC3339)
	challenge := fmt.Sprintf("agent-secrets:%s:%s:%s:%s", agentID, deploymentID, nonce, signedAt)
	signature, err := pki.SignMessage(keyPEM, []byte(challenge))
	if err != nil {
		return nil, 0, fmt.Errorf("sign secrets challenge: %w", err)
	}

	req, err := http.NewRequest(http.MethodGet, baseURL+"/api/v1/cluster-agents/"+agentID+"/deployments/"+deploymentID+"/secrets", nil)
	if err != nil {
		return nil, 0, err
	}
	req.Header.Set("X-Agent-Nonce", nonce)
	req.Header.Set("X-Agent-Signed-At", signedAt)
	req.Header.Set("X-Agent-Signature", signature)

	resp, err := c.Do(req)
	if err != nil {
		return nil, 0, err
	}
	defer func() { _ = resp.Body.Close() }()
	respBody, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK {
		return nil, resp.StatusCode, fmt.Errorf("fetch secrets failed: HTTP %d: %s", resp.StatusCode, string(respBody))
	}
	var parsed struct {
		Secrets map[string]string `json:"secrets"`
	}
	if err := json.Unmarshal(respBody, &parsed); err != nil {
		return nil, resp.StatusCode, fmt.Errorf("parse secrets response: %w", err)
	}
	return parsed.Secrets, resp.StatusCode, nil
}

// fetchSecretsWithAttestationRetry is Milestone 8's addition to the
// deploy/rollback path: it tries fetchAgentSecrets first (the common case,
// no confidential-computing requirement), and only if that is rejected
// with HTTP 409 (control-api's "requires a fresh, passing attestation
// result" response) does it run the remote-attestation protocol -- request
// a server-issued challenge, produce mock evidence, submit it for
// verification -- before retrying the exact same secrets fetch once.
func fetchSecretsWithAttestationRetry(c *http.Client, baseURL, keyPEM, agentID, deploymentID string) (map[string]string, error) {
	secrets, status, err := fetchAgentSecrets(c, baseURL, keyPEM, agentID, deploymentID)
	if err == nil {
		return secrets, nil
	}
	if status != http.StatusConflict {
		return nil, err
	}

	fmt.Println("mockclusteragent: secrets fetch requires confidential-computing attestation; running the remote-attestation protocol...")
	sessionID, sessionNonce, err := requestAttestationSession(c, baseURL, keyPEM, agentID)
	if err != nil {
		return nil, fmt.Errorf("request attestation session: %w", err)
	}
	decision, reasonCodes, err := submitAttestationEvidence(c, baseURL, keyPEM, agentID, sessionID, deploymentID, sessionNonce, mockMeasurements())
	if err != nil {
		return nil, fmt.Errorf("submit attestation evidence: %w", err)
	}
	fmt.Printf("mockclusteragent: attestation decision: %s %v\n", decision, reasonCodes)
	if decision != "pass" {
		return nil, fmt.Errorf("attestation failed: %v", reasonCodes)
	}

	secrets, _, err = fetchAgentSecrets(c, baseURL, keyPEM, agentID, deploymentID)
	if err != nil {
		return nil, fmt.Errorf("fetch secrets after successful attestation: %w", err)
	}
	return secrets, nil
}

// mockMeasurements is this agent's fixed, simulated hardware report -- a
// real cluster agent running inside genuine confidential-computing hardware
// would read these values from the platform itself (e.g. an SEV-SNP
// attestation report or a TDX quote); this mock has no real hardware
// behind it at all; see internal/platform/attestation.MockProvider's own
// doc comment on why this makes no claim of proving genuine confidential
// computing.
func mockMeasurements() map[string]any {
	return map[string]any{
		"platform":      "mock-tee-v1",
		"firmware_hash": "mock-firmware-abc123",
	}
}

// requestAttestationSession proves identity by signing a canonical
// challenge string (the same construction pollPendingMessages uses for its
// own GET-shaped auth), and returns the server-issued session id and
// attestation nonce the subsequent evidence submission must embed.
func requestAttestationSession(c *http.Client, baseURL, keyPEM, agentID string) (sessionID, attestationNonce string, err error) {
	requestNonce := fmt.Sprintf("attsess-%d", time.Now().UnixNano())
	signedAt := time.Now().UTC().Format(time.RFC3339)
	challenge := fmt.Sprintf("attestation-session:%s:%s:%s", agentID, requestNonce, signedAt)
	signature, err := pki.SignMessage(keyPEM, []byte(challenge))
	if err != nil {
		return "", "", fmt.Errorf("sign session request: %w", err)
	}

	body, err := json.Marshal(map[string]string{"nonce": requestNonce, "signed_at": signedAt, "signature": signature})
	if err != nil {
		return "", "", err
	}
	req, err := http.NewRequest(http.MethodPost, baseURL+"/api/v1/cluster-agents/"+agentID+"/attestation-sessions", bytes.NewReader(body))
	if err != nil {
		return "", "", err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.Do(req)
	if err != nil {
		return "", "", err
	}
	defer func() { _ = resp.Body.Close() }()
	respBody, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusCreated {
		return "", "", fmt.Errorf("request attestation session failed: HTTP %d: %s", resp.StatusCode, string(respBody))
	}
	var parsed struct {
		ID    string `json:"id"`
		Nonce string `json:"nonce"`
	}
	if err := json.Unmarshal(respBody, &parsed); err != nil {
		return "", "", fmt.Errorf("parse attestation session response: %w", err)
	}
	return parsed.ID, parsed.Nonce, nil
}

// submitAttestationEvidence signs its own JSON body (the session's nonce,
// among other fields, is covered by this same signature) and submits it to
// control-api for verification against the cluster's active attestation
// policy.
func submitAttestationEvidence(c *http.Client, baseURL, keyPEM, agentID, sessionID, deploymentID, sessionNonce string, measurements map[string]any) (decision string, reasonCodes []string, err error) {
	body, err := json.Marshal(map[string]any{
		"deployment_id": deploymentID,
		"provider_type": "mock",
		"measurements":  measurements,
		"raw_evidence":  `{"note":"fictional mock evidence blob, not a real attestation report"}`,
		"nonce":         sessionNonce,
		"signed_at":     time.Now().UTC().Format(time.RFC3339),
	})
	if err != nil {
		return "", nil, err
	}
	signature, err := pki.SignMessage(keyPEM, body)
	if err != nil {
		return "", nil, fmt.Errorf("sign evidence: %w", err)
	}

	req, err := http.NewRequest(http.MethodPost, baseURL+"/api/v1/cluster-agents/"+agentID+"/attestation-sessions/"+sessionID+"/evidence", bytes.NewReader(body))
	if err != nil {
		return "", nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Agent-Signature", signature)

	resp, err := c.Do(req)
	if err != nil {
		return "", nil, err
	}
	defer func() { _ = resp.Body.Close() }()
	respBody, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusCreated {
		return "", nil, fmt.Errorf("submit evidence failed: HTTP %d: %s", resp.StatusCode, string(respBody))
	}
	var parsed struct {
		Decision    string   `json:"decision"`
		ReasonCodes []string `json:"reason_codes"`
	}
	if err := json.Unmarshal(respBody, &parsed); err != nil {
		return "", nil, fmt.Errorf("parse evidence result: %w", err)
	}
	return parsed.Decision, parsed.ReasonCodes, nil
}

// reportCommandResult signs its own JSON body (action, success, detail,
// nonce, and signed_at all covered by the same signature) and submits it to
// the deployments-owned command-result endpoint -- the Milestone 7
// counterpart to respond(), which remains deployment_plan_validate's own
// endpoint and cannot handle this newer message type (see control-api's
// AgentReportCommandResult doc comment).
func reportCommandResult(c *http.Client, baseURL, keyPEM, agentID, messageID, action string, success bool, detail string) error {
	body, err := json.Marshal(map[string]any{
		"action":    action,
		"success":   success,
		"detail":    detail,
		"nonce":     fmt.Sprintf("command-result-%d", time.Now().UnixNano()),
		"signed_at": time.Now().UTC().Format(time.RFC3339),
	})
	if err != nil {
		return err
	}
	signature, err := pki.SignMessage(keyPEM, body)
	if err != nil {
		return fmt.Errorf("sign command result: %w", err)
	}

	req, err := http.NewRequest(http.MethodPost, baseURL+"/api/v1/cluster-agents/"+agentID+"/control-messages/"+messageID+"/command-result", bytes.NewReader(body))
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
		return fmt.Errorf("report command result failed: HTTP %d: %s", resp.StatusCode, string(respBody))
	}
	return nil
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
