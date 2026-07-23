package images

import (
	"context"
	"crypto/ecdsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/pem"
	"errors"
	"fmt"
	"regexp"
	"time"

	"github.com/google/uuid"

	"gridkeep/control-api/internal/modules/rbac"
	"gridkeep/control-api/internal/platform/audit"
	dbpkg "gridkeep/control-api/internal/platform/db"
	"gridkeep/control-api/internal/platform/httpserver"
)

var (
	ErrRegistryNotApproved          = errors.New("registry host is not on the platform-approved registry allowlist")
	ErrImageNotFound                = errors.New("container image not found")
	ErrImageNotPending              = errors.New("container image is not pending or blocked, so it cannot be approved")
	ErrImageNotApproved             = errors.New("container image is not approved")
	ErrBlockedByVulnerabilityPolicy = errors.New("image approval blocked by the tenant's vulnerability policy")
	ErrExceptionNotFound            = errors.New("vulnerability exception not found")
	ErrExceptionNotPending          = errors.New("vulnerability exception is not pending")
	ErrCannotSelfApproveException   = errors.New("the same user cannot both request and approve a vulnerability exception")
)

var digestPattern = regexp.MustCompile(`^sha256:[a-f0-9]{64}$`)

// severityRank orders vulnerability severities from least (0) to most (4)
// severe, so a policy's max_allowed_severity can be compared against a
// finding's severity with a simple integer comparison.
var severityRank = map[string]int{"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}

type Service struct {
	store *dbpkg.Store
}

func NewService(store *dbpkg.Store) *Service {
	return &Service{store: store}
}

func actorFromContext(ctx context.Context) uuid.UUID {
	if authUser, ok := httpserver.AuthUser(ctx); ok {
		return authUser.UserID
	}
	return uuid.Nil
}

// ---------------------------------------------------------------------
// approved_container_registries (platform-scoped)
// ---------------------------------------------------------------------

func (s *Service) ListApprovedRegistries(ctx context.Context) ([]ApprovedRegistry, error) {
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listApprovedRegistries(ctx, scopedTx.Tx)
}

func (s *Service) AddApprovedRegistry(ctx context.Context, registryHost, notes string) (ApprovedRegistry, error) {
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	reg, err := addApprovedRegistry(ctx, scopedTx.Tx, registryHost, notes, actor)
	if err != nil {
		return ApprovedRegistry{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopePlatform,
		Action: "images.registry_approved", TargetType: "approved_container_registry", TargetID: &reg.ID,
		Evidence: map[string]any{"registry_host": registryHost},
	}); err != nil {
		return ApprovedRegistry{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return ApprovedRegistry{}, err
	}
	return reg, nil
}

func (s *Service) SetApprovedRegistryActive(ctx context.Context, id uuid.UUID, isActive bool) error {
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	ok, err := setApprovedRegistryActive(ctx, scopedTx.Tx, id, isActive)
	if err != nil {
		return err
	}
	if !ok {
		return ErrImageNotFound
	}
	action := "images.registry_deactivated"
	if isActive {
		action = "images.registry_reactivated"
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopePlatform,
		Action: action, TargetType: "approved_container_registry", TargetID: &id,
	}); err != nil {
		return err
	}
	return scopedTx.Commit(ctx)
}

// ---------------------------------------------------------------------
// container_images
// ---------------------------------------------------------------------

func (s *Service) ListImages(ctx context.Context) ([]ContainerImage, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listImages(ctx, scopedTx.Tx, *scope.TenantID)
}

func (s *Service) GetImage(ctx context.Context, id uuid.UUID) (ContainerImage, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	img, exists, err := getImageByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return ContainerImage{}, err
	}
	if !exists {
		return ContainerImage{}, ErrImageNotFound
	}
	return img, nil
}

// RegisterImage records a new container image by content digest -- never by
// a mutable tag alone. The registry host must be on the platform-approved
// allowlist; this fails closed (an unrecognized or deactivated registry
// host is rejected, not silently allowed through).
func (s *Service) RegisterImage(ctx context.Context, registryHost, repository, digest, tag string) (ContainerImage, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	if !digestPattern.MatchString(digest) {
		return ContainerImage{}, fmt.Errorf("%w: digest must match sha256:<64 hex characters>", errors.New("invalid digest format"))
	}
	approved, err := isRegistryApproved(ctx, scopedTx.Tx, registryHost)
	if err != nil {
		return ContainerImage{}, err
	}
	if !approved {
		return ContainerImage{}, ErrRegistryNotApproved
	}

	img, err := createImage(ctx, scopedTx.Tx, *scope.TenantID, registryHost, repository, digest, tag, actor)
	if err != nil {
		return ContainerImage{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor,
		ScopeType:   audit.ScopeEnterprise,
		ScopeID:     scope.TenantID,
		Action:      "images.registered",
		TargetType:  "container_image",
		TargetID:    &img.ID,
		Evidence:    map[string]any{"registry_host": registryHost, "repository": repository, "digest": digest},
	}); err != nil {
		return ContainerImage{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return ContainerImage{}, err
	}
	return img, nil
}

// ApproveImage evaluates the tenant's vulnerability policy (creating a
// default one on first use) against the image's SBOM presence, signature
// status, and most recent vulnerability scan findings, blocking approval
// -- fails closed -- unless every requirement is satisfied or covered by an
// active, approved, unexpired exception.
func (s *Service) ApproveImage(ctx context.Context, id uuid.UUID) (ContainerImage, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	img, exists, err := getImageByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return ContainerImage{}, err
	}
	if !exists {
		return ContainerImage{}, ErrImageNotFound
	}
	if img.Status != "pending" && img.Status != "blocked" {
		return ContainerImage{}, ErrImageNotPending
	}

	policy, exists, err := getVulnerabilityPolicy(ctx, scopedTx.Tx, *scope.TenantID)
	if err != nil {
		return ContainerImage{}, err
	}
	if !exists {
		policy, err = createDefaultVulnerabilityPolicy(ctx, scopedTx.Tx, *scope.TenantID)
		if err != nil {
			return ContainerImage{}, err
		}
	}

	var blockReasons []string

	if policy.RequireSBOM {
		ok, err := hasSBOM(ctx, scopedTx.Tx, id)
		if err != nil {
			return ContainerImage{}, err
		}
		if !ok {
			blockReasons = append(blockReasons, "SBOM_REQUIRED_BUT_MISSING")
		}
	}
	if policy.BlockUnsignedImages {
		ok, err := hasVerifiedSignature(ctx, scopedTx.Tx, id)
		if err != nil {
			return ContainerImage{}, err
		}
		if !ok {
			blockReasons = append(blockReasons, "SIGNATURE_REQUIRED_BUT_MISSING")
		}
	}

	findings, err := latestScanFindings(ctx, scopedTx.Tx, id)
	if err != nil {
		return ContainerImage{}, err
	}
	maxAllowed := severityRank[policy.MaxAllowedSeverity]
	for _, f := range findings {
		if severityRank[f.Severity] <= maxAllowed {
			continue
		}
		covered, err := activeExceptionCoversFinding(ctx, scopedTx.Tx, id, f.ID)
		if err != nil {
			return ContainerImage{}, err
		}
		if !covered {
			blockReasons = append(blockReasons, fmt.Sprintf("VULNERABILITY_POLICY_VIOLATION:%s:%s", f.CVEID, f.Severity))
		}
	}

	if len(blockReasons) > 0 {
		if err := markImageBlocked(ctx, scopedTx.Tx, id); err != nil {
			return ContainerImage{}, err
		}
		if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
			ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
			Action: "images.approval_blocked", TargetType: "container_image", TargetID: &id,
			Evidence: map[string]any{"reasons": blockReasons},
		}); err != nil {
			return ContainerImage{}, err
		}
		if err := scopedTx.Commit(ctx); err != nil {
			return ContainerImage{}, err
		}
		return ContainerImage{}, fmt.Errorf("%w: %v", ErrBlockedByVulnerabilityPolicy, blockReasons)
	}

	ok, err := markImageApproved(ctx, scopedTx.Tx, id, actor)
	if err != nil {
		return ContainerImage{}, err
	}
	if !ok {
		return ContainerImage{}, ErrImageNotPending
	}
	approved, exists, err := getImageByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return ContainerImage{}, err
	}
	if !exists {
		return ContainerImage{}, ErrImageNotFound
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "images.approved", TargetType: "container_image", TargetID: &id,
	}); err != nil {
		return ContainerImage{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return ContainerImage{}, err
	}
	return approved, nil
}

// RevokeImage is the emergency "untrust immediately" action -- an approved
// image found to be compromised or otherwise unsafe after the fact.
func (s *Service) RevokeImage(ctx context.Context, id uuid.UUID, reason string) (ContainerImage, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	ok, err := markImageRevoked(ctx, scopedTx.Tx, id, reason)
	if err != nil {
		return ContainerImage{}, err
	}
	if !ok {
		return ContainerImage{}, ErrImageNotApproved
	}
	img, exists, err := getImageByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return ContainerImage{}, err
	}
	if !exists {
		return ContainerImage{}, ErrImageNotFound
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "images.revoked", TargetType: "container_image", TargetID: &id,
		Evidence: map[string]any{"reason": reason},
	}); err != nil {
		return ContainerImage{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return ContainerImage{}, err
	}
	return img, nil
}

// ---------------------------------------------------------------------
// signatures -- real ECDSA verification, never a fabricated result
// ---------------------------------------------------------------------

// RecordSignature verifies signatureBase64 as a genuine ECDSA signature
// (over the SHA-256 hash of the image's digest string) made with the
// private key corresponding to publicKeyPEM. The stored status reflects
// only what was actually verified: "verified" if, and only if, the
// signature check passes; "invalid" for every other outcome (malformed
// PEM, wrong key type, malformed signature, or a signature that doesn't
// match) -- there is no code path that stores "verified" without a
// successful cryptographic check.
func (s *Service) RecordSignature(ctx context.Context, imageID uuid.UUID, signer, publicKeyPEM, signatureBase64 string, signedAt *time.Time) (Signature, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	img, exists, err := getImageByID(ctx, scopedTx.Tx, *scope.TenantID, imageID)
	if err != nil {
		return Signature{}, err
	}
	if !exists {
		return Signature{}, ErrImageNotFound
	}

	status := "invalid"
	if verifyECDSASignature(publicKeyPEM, signatureBase64, img.Digest) {
		status = "verified"
	}

	sig, err := createSignature(ctx, scopedTx.Tx, *scope.TenantID, imageID, signer, publicKeyPEM, signatureBase64, status, signedAt)
	if err != nil {
		return Signature{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "images.signature_recorded", TargetType: "container_image", TargetID: &imageID,
		Evidence: map[string]any{"signer": signer, "status": status},
	}); err != nil {
		return Signature{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Signature{}, err
	}
	return sig, nil
}

func verifyECDSASignature(publicKeyPEM, signatureBase64, message string) bool {
	block, _ := pem.Decode([]byte(publicKeyPEM))
	if block == nil {
		return false
	}
	pub, err := x509.ParsePKIXPublicKey(block.Bytes)
	if err != nil {
		return false
	}
	ecdsaPub, ok := pub.(*ecdsa.PublicKey)
	if !ok {
		return false
	}
	sigBytes, err := base64.StdEncoding.DecodeString(signatureBase64)
	if err != nil {
		return false
	}
	hash := sha256.Sum256([]byte(message))
	return ecdsa.VerifyASN1(ecdsaPub, hash[:], sigBytes)
}

func (s *Service) ListSignatures(ctx context.Context, imageID uuid.UUID) ([]Signature, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listSignatures(ctx, scopedTx.Tx, *scope.TenantID, imageID)
}

// ---------------------------------------------------------------------
// provenance
// ---------------------------------------------------------------------

func (s *Service) RecordProvenance(ctx context.Context, imageID uuid.UUID, builder, sourceRepository, buildCommit, buildPipelineURL string, attestation map[string]any) (Provenance, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	p, err := upsertProvenance(ctx, scopedTx.Tx, *scope.TenantID, imageID, builder, sourceRepository, buildCommit, buildPipelineURL, attestation, actor)
	if err != nil {
		return Provenance{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "images.provenance_recorded", TargetType: "container_image", TargetID: &imageID,
	}); err != nil {
		return Provenance{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Provenance{}, err
	}
	return p, nil
}

func (s *Service) GetProvenance(ctx context.Context, imageID uuid.UUID) (Provenance, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	p, exists, err := getProvenance(ctx, scopedTx.Tx, *scope.TenantID, imageID)
	if err != nil {
		return Provenance{}, err
	}
	if !exists {
		return Provenance{}, ErrImageNotFound
	}
	return p, nil
}

// ---------------------------------------------------------------------
// SBOMs
// ---------------------------------------------------------------------

func (s *Service) IngestSBOM(ctx context.Context, imageID uuid.UUID, format string, document map[string]any, generatedBy string) (SBOM, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	sbom, err := createSBOM(ctx, scopedTx.Tx, *scope.TenantID, imageID, format, document, generatedBy, actor)
	if err != nil {
		return SBOM{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "images.sbom_ingested", TargetType: "container_image", TargetID: &imageID,
		Evidence: map[string]any{"format": format},
	}); err != nil {
		return SBOM{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return SBOM{}, err
	}
	return sbom, nil
}

func (s *Service) ListSBOMs(ctx context.Context, imageID uuid.UUID) ([]SBOM, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listSBOMs(ctx, scopedTx.Tx, *scope.TenantID, imageID)
}

// ---------------------------------------------------------------------
// vulnerability scans / findings
// ---------------------------------------------------------------------

func (s *Service) IngestVulnerabilityScan(ctx context.Context, imageID uuid.UUID, scanner string, scannedAt time.Time, findings []FindingInput) (VulnerabilityScan, []VulnerabilityFinding, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	scan, createdFindings, err := createVulnerabilityScan(ctx, scopedTx.Tx, *scope.TenantID, imageID, scanner, scannedAt, findings, actor)
	if err != nil {
		return VulnerabilityScan{}, nil, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "images.vulnerability_scan_ingested", TargetType: "container_image", TargetID: &imageID,
		Evidence: map[string]any{"scanner": scanner, "finding_count": len(createdFindings)},
	}); err != nil {
		return VulnerabilityScan{}, nil, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return VulnerabilityScan{}, nil, err
	}
	return scan, createdFindings, nil
}

func (s *Service) ListVulnerabilityScans(ctx context.Context, imageID uuid.UUID) ([]VulnerabilityScan, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listVulnerabilityScans(ctx, scopedTx.Tx, *scope.TenantID, imageID)
}

func (s *Service) ListFindings(ctx context.Context, scanID uuid.UUID) ([]VulnerabilityFinding, error) {
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listFindingsForScan(ctx, scopedTx.Tx, scanID)
}

// ---------------------------------------------------------------------
// vulnerability policy
// ---------------------------------------------------------------------

func (s *Service) GetVulnerabilityPolicy(ctx context.Context) (VulnerabilityPolicy, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	policy, exists, err := getVulnerabilityPolicy(ctx, scopedTx.Tx, *scope.TenantID)
	if err != nil {
		return VulnerabilityPolicy{}, err
	}
	if !exists {
		created, err := createDefaultVulnerabilityPolicy(ctx, scopedTx.Tx, *scope.TenantID)
		if err != nil {
			return VulnerabilityPolicy{}, err
		}
		if err := scopedTx.Commit(ctx); err != nil {
			return VulnerabilityPolicy{}, err
		}
		return created, nil
	}
	return policy, nil
}

func (s *Service) UpdateVulnerabilityPolicy(ctx context.Context, maxAllowedSeverity string, blockUnsigned, requireSBOM bool) (VulnerabilityPolicy, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	if _, exists, err := getVulnerabilityPolicy(ctx, scopedTx.Tx, *scope.TenantID); err != nil {
		return VulnerabilityPolicy{}, err
	} else if !exists {
		if _, err := createDefaultVulnerabilityPolicy(ctx, scopedTx.Tx, *scope.TenantID); err != nil {
			return VulnerabilityPolicy{}, err
		}
	}

	policy, err := updateVulnerabilityPolicy(ctx, scopedTx.Tx, *scope.TenantID, maxAllowedSeverity, blockUnsigned, requireSBOM, actor)
	if err != nil {
		return VulnerabilityPolicy{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "images.vulnerability_policy_updated", TargetType: "vulnerability_policy", TargetID: &policy.ID,
		Evidence: map[string]any{"max_allowed_severity": maxAllowedSeverity, "block_unsigned_images": blockUnsigned, "require_sbom": requireSBOM},
	}); err != nil {
		return VulnerabilityPolicy{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return VulnerabilityPolicy{}, err
	}
	return policy, nil
}

// ---------------------------------------------------------------------
// vulnerability exceptions -- dual control
// ---------------------------------------------------------------------

func (s *Service) RequestException(ctx context.Context, imageID uuid.UUID, findingID *uuid.UUID, reason string, expiresAt time.Time) (VulnerabilityException, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	e, err := createException(ctx, scopedTx.Tx, *scope.TenantID, imageID, findingID, actor, reason, expiresAt)
	if err != nil {
		return VulnerabilityException{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "images.vulnerability_exception_requested", TargetType: "container_image", TargetID: &imageID,
		Evidence: map[string]any{"reason": reason, "expires_at": expiresAt},
	}); err != nil {
		return VulnerabilityException{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return VulnerabilityException{}, err
	}
	return e, nil
}

// ApproveException is dual control: a genuinely different user than
// whoever called RequestException, enforced both here and by the
// vulnerability_exceptions_no_self_approval DB CHECK constraint.
func (s *Service) ApproveException(ctx context.Context, id uuid.UUID) (VulnerabilityException, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	e, exists, err := getExceptionByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return VulnerabilityException{}, err
	}
	if !exists {
		return VulnerabilityException{}, ErrExceptionNotFound
	}
	if e.Status != "pending" {
		return VulnerabilityException{}, ErrExceptionNotPending
	}
	if e.RequestedBy == actor {
		return VulnerabilityException{}, ErrCannotSelfApproveException
	}

	ok, err := markExceptionApproved(ctx, scopedTx.Tx, id, actor)
	if err != nil {
		return VulnerabilityException{}, err
	}
	if !ok {
		return VulnerabilityException{}, ErrExceptionNotPending
	}
	approved, exists, err := getExceptionByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return VulnerabilityException{}, err
	}
	if !exists {
		return VulnerabilityException{}, ErrExceptionNotFound
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "images.vulnerability_exception_approved", TargetType: "vulnerability_exception", TargetID: &id,
		Evidence: map[string]any{"requested_by": e.RequestedBy},
	}); err != nil {
		return VulnerabilityException{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return VulnerabilityException{}, err
	}
	return approved, nil
}

func (s *Service) RejectException(ctx context.Context, id uuid.UUID) (VulnerabilityException, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	ok, err := markExceptionRejected(ctx, scopedTx.Tx, id)
	if err != nil {
		return VulnerabilityException{}, err
	}
	if !ok {
		return VulnerabilityException{}, ErrExceptionNotPending
	}
	e, exists, err := getExceptionByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return VulnerabilityException{}, err
	}
	if !exists {
		return VulnerabilityException{}, ErrExceptionNotFound
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor, ScopeType: audit.ScopeEnterprise, ScopeID: scope.TenantID,
		Action: "images.vulnerability_exception_rejected", TargetType: "vulnerability_exception", TargetID: &id,
	}); err != nil {
		return VulnerabilityException{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return VulnerabilityException{}, err
	}
	return e, nil
}

func (s *Service) ListExceptions(ctx context.Context, imageID uuid.UUID) ([]VulnerabilityException, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listExceptionsForImage(ctx, scopedTx.Tx, *scope.TenantID, imageID)
}
