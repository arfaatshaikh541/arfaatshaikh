package artefacts

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"time"

	"github.com/google/uuid"

	"gridkeep/control-api/internal/modules/rbac"
	"gridkeep/control-api/internal/platform/audit"
	dbpkg "gridkeep/control-api/internal/platform/db"
	"gridkeep/control-api/internal/platform/httpserver"
	"gridkeep/control-api/internal/platform/storage"
)

var (
	ErrNotFound                = errors.New("artefact not found")
	ErrNotPending              = errors.New("artefact upload is not pending completion")
	ErrNotAvailable            = errors.New("artefact is not available for download")
	ErrInfected                = errors.New("artefact failed malware scanning and cannot be downloaded")
	ErrContentTooLarge         = errors.New("declared content length exceeds the maximum allowed artefact size")
	ErrContentTypeNotAllowed   = errors.New("content type is not allowed for this artefact purpose")
	ErrUploadNotFoundInStorage = errors.New("no object was found in storage at the authorised upload location")
	ErrSizeMismatch            = errors.New("uploaded object size does not match the declared content length")
	ErrChecksumMismatch        = errors.New("uploaded object checksum does not match the declared checksum")
)

// Config bounds what AuthoriseUpload will accept. AllowedContentTypes being
// empty means "no content-type allowlist configured" -- every purpose this
// module knows about today sets one (see app.go wiring), so this only
// matters for tests/defaults.
type Config struct {
	MaxContentLength    int64
	AllowedContentTypes map[string]bool
	UploadURLTTL        time.Duration
	DownloadURLTTL      time.Duration
}

// ObjectStore is the subset of *storage.Client this service needs -- an
// interface so integration tests can substitute an in-memory fake instead
// of requiring a live MinIO instance (mirroring how Milestone 3 tested
// against a fake policy-engine rather than a live Python process).
type ObjectStore interface {
	Bucket() string
	PresignedPutURL(ctx context.Context, objectKey string, expiry time.Duration) (string, error)
	PresignedGetURL(ctx context.Context, objectKey string, expiry time.Duration) (string, error)
	Stat(ctx context.Context, objectKey string) (storage.ObjectInfo, error)
	Get(ctx context.Context, objectKey string) (io.ReadCloser, error)
	Remove(ctx context.Context, objectKey string) error
}

type Service struct {
	store   *dbpkg.Store
	storage ObjectStore
	cfg     Config
}

func NewService(store *dbpkg.Store, objectStore ObjectStore, cfg Config) *Service {
	return &Service{store: store, storage: objectStore, cfg: cfg}
}

func actorFromContext(ctx context.Context) uuid.UUID {
	if authUser, ok := httpserver.AuthUser(ctx); ok {
		return authUser.UserID
	}
	return uuid.Nil
}

// AuthoriseUpload validates the declared upload metadata, mints a
// non-guessable, tenant-isolated object key, and returns a short-lived
// presigned PUT URL the caller uploads directly to -- the object's bytes
// never pass through control-api.
func (s *Service) AuthoriseUpload(ctx context.Context, purpose, contentType string, contentLength int64) (Upload, string, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	if contentLength <= 0 || contentLength > s.cfg.MaxContentLength {
		return Upload{}, "", ErrContentTooLarge
	}
	if len(s.cfg.AllowedContentTypes) > 0 && !s.cfg.AllowedContentTypes[contentType] {
		return Upload{}, "", ErrContentTypeNotAllowed
	}

	objectKey := storage.ObjectKey(*scope.TenantID, nil)
	upload, err := createUpload(ctx, scopedTx.Tx, *scope.TenantID, nil, objectKey, s.storage.Bucket(), purpose, contentType, contentLength, actor, map[string]any{})
	if err != nil {
		return Upload{}, "", err
	}

	uploadURL, err := s.storage.PresignedPutURL(ctx, objectKey, s.cfg.UploadURLTTL)
	if err != nil {
		return Upload{}, "", fmt.Errorf("presign upload url: %w", err)
	}

	if err := createAccessGrant(ctx, scopedTx.Tx, *scope.TenantID, upload.ID, actor, "upload", time.Now().Add(s.cfg.UploadURLTTL)); err != nil {
		return Upload{}, "", err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor,
		ScopeType:   audit.ScopeEnterprise,
		ScopeID:     scope.TenantID,
		Action:      "artefacts.upload_authorised",
		TargetType:  "artefact_upload",
		TargetID:    &upload.ID,
		Evidence:    map[string]any{"purpose": purpose, "content_type": contentType, "content_length": contentLength},
	}); err != nil {
		return Upload{}, "", err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Upload{}, "", err
	}
	return upload, uploadURL, nil
}

// CompleteUpload independently verifies with the storage backend that the
// object actually exists and matches the declared size, then streams and
// hashes the object's real bytes to verify the declared checksum -- an
// artefact is never marked "uploaded" on the client's unverified say-so.
func (s *Service) CompleteUpload(ctx context.Context, id uuid.UUID, declaredChecksum string) (Upload, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)

	upload, exists, err := getUploadByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return Upload{}, err
	}
	if !exists {
		return Upload{}, ErrNotFound
	}
	if upload.Status != "pending" {
		return Upload{}, ErrNotPending
	}

	info, statErr := s.storage.Stat(ctx, upload.ObjectKey)
	if statErr != nil {
		_, _ = markFailed(ctx, scopedTx.Tx, id)
		_ = s.recordFailure(ctx, scopedTx, scope, id, "object_not_found_in_storage")
		if commitErr := scopedTx.Commit(ctx); commitErr != nil {
			return Upload{}, commitErr
		}
		return Upload{}, ErrUploadNotFoundInStorage
	}

	if upload.ContentLength != nil && info.Size != *upload.ContentLength {
		_, _ = markFailed(ctx, scopedTx.Tx, id)
		_ = s.recordFailure(ctx, scopedTx, scope, id, "size_mismatch")
		if commitErr := scopedTx.Commit(ctx); commitErr != nil {
			return Upload{}, commitErr
		}
		return Upload{}, ErrSizeMismatch
	}

	actualChecksum, err := s.hashObject(ctx, upload.ObjectKey)
	if err != nil {
		return Upload{}, fmt.Errorf("hash uploaded object: %w", err)
	}
	if declaredChecksum != "" && actualChecksum != declaredChecksum {
		_, _ = markFailed(ctx, scopedTx.Tx, id)
		_ = s.recordFailure(ctx, scopedTx, scope, id, "checksum_mismatch")
		if commitErr := scopedTx.Commit(ctx); commitErr != nil {
			return Upload{}, commitErr
		}
		return Upload{}, ErrChecksumMismatch
	}

	if _, err := markUploaded(ctx, scopedTx.Tx, id, info.Size, actualChecksum, info.VersionID); err != nil {
		return Upload{}, err
	}
	actor := actorFromContext(ctx)
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor,
		ScopeType:   audit.ScopeEnterprise,
		ScopeID:     scope.TenantID,
		Action:      "artefacts.upload_completed",
		TargetType:  "artefact_upload",
		TargetID:    &id,
		Evidence:    map[string]any{"size": info.Size, "checksum_sha256": actualChecksum},
	}); err != nil {
		return Upload{}, err
	}
	updated, _, err := getUploadByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return Upload{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Upload{}, err
	}
	return updated, nil
}

func (s *Service) recordFailure(ctx context.Context, tx *rbac.ScopedTx, scope rbac.Scope, id uuid.UUID, reason string) error {
	actor := actorFromContext(ctx)
	return audit.Record(ctx, tx.Tx, audit.Event{
		ActorUserID: &actor,
		ScopeType:   audit.ScopeEnterprise,
		ScopeID:     scope.TenantID,
		Action:      "artefacts.upload_failed",
		TargetType:  "artefact_upload",
		TargetID:    &id,
		Evidence:    map[string]any{"reason": reason},
	})
}

func (s *Service) hashObject(ctx context.Context, objectKey string) (string, error) {
	reader, err := s.storage.Get(ctx, objectKey)
	if err != nil {
		return "", err
	}
	defer func() { _ = reader.Close() }()
	h := sha256.New()
	if _, err := io.Copy(h, reader); err != nil {
		return "", fmt.Errorf("read object for hashing: %w", err)
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

// RequestDownload issues a short-lived presigned GET URL. It fails closed
// on anything other than a confirmed-uploaded, not-infected artefact --
// there is no path that hands out a download URL for a pending, failed, or
// malware-flagged object.
func (s *Service) RequestDownload(ctx context.Context, id uuid.UUID) (string, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	upload, exists, err := getUploadByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return "", err
	}
	if !exists {
		return "", ErrNotFound
	}
	if upload.Status != "uploaded" && upload.Status != "verified" {
		return "", ErrNotAvailable
	}
	if upload.MalwareScanStatus == "infected" {
		return "", ErrInfected
	}

	url, err := s.storage.PresignedGetURL(ctx, upload.ObjectKey, s.cfg.DownloadURLTTL)
	if err != nil {
		return "", fmt.Errorf("presign download url: %w", err)
	}
	if err := createAccessGrant(ctx, scopedTx.Tx, *scope.TenantID, id, actor, "download", time.Now().Add(s.cfg.DownloadURLTTL)); err != nil {
		return "", err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor,
		ScopeType:   audit.ScopeEnterprise,
		ScopeID:     scope.TenantID,
		Action:      "artefacts.downloaded",
		TargetType:  "artefact_upload",
		TargetID:    &id,
	}); err != nil {
		return "", err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return "", err
	}
	return url, nil
}

// MarkMalwareScanResult records a real scan outcome reported by an external
// scanner integration. It never fabricates a "clean" result on its own --
// this method only stores whatever evidence its caller actually provides.
func (s *Service) MarkMalwareScanResult(ctx context.Context, id uuid.UUID, result string) (Upload, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	ok, err := setMalwareScanStatus(ctx, scopedTx.Tx, id, result)
	if err != nil {
		return Upload{}, err
	}
	if !ok {
		return Upload{}, ErrNotFound
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor,
		ScopeType:   audit.ScopeEnterprise,
		ScopeID:     scope.TenantID,
		Action:      "artefacts.malware_scan_recorded",
		TargetType:  "artefact_upload",
		TargetID:    &id,
		Evidence:    map[string]any{"result": result},
	}); err != nil {
		return Upload{}, err
	}
	updated, _, err := getUploadByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return Upload{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Upload{}, err
	}
	return updated, nil
}

// DeleteArtefact removes the object from storage (the bucket's versioning
// retains prior versions, so this is a recoverable "soft" delete from
// storage's point of view) and marks the metadata row deleted.
func (s *Service) DeleteArtefact(ctx context.Context, id uuid.UUID) (Upload, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	actor := actorFromContext(ctx)

	upload, exists, err := getUploadByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return Upload{}, err
	}
	if !exists {
		return Upload{}, ErrNotFound
	}

	if err := s.storage.Remove(ctx, upload.ObjectKey); err != nil {
		return Upload{}, fmt.Errorf("remove object from storage: %w", err)
	}
	if _, err := markDeleted(ctx, scopedTx.Tx, id, actor); err != nil {
		return Upload{}, err
	}
	if err := audit.Record(ctx, scopedTx.Tx, audit.Event{
		ActorUserID: &actor,
		ScopeType:   audit.ScopeEnterprise,
		ScopeID:     scope.TenantID,
		Action:      "artefacts.deleted",
		TargetType:  "artefact_upload",
		TargetID:    &id,
	}); err != nil {
		return Upload{}, err
	}
	updated, _, err := getUploadByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return Upload{}, err
	}
	if err := scopedTx.Commit(ctx); err != nil {
		return Upload{}, err
	}
	return updated, nil
}

func (s *Service) ListArtefacts(ctx context.Context) ([]Upload, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	return listUploads(ctx, scopedTx.Tx, *scope.TenantID)
}

func (s *Service) GetArtefact(ctx context.Context, id uuid.UUID) (Upload, error) {
	scope, _ := rbac.FromContext(ctx)
	scopedTx, _ := rbac.TxFromContext(ctx)
	u, exists, err := getUploadByID(ctx, scopedTx.Tx, *scope.TenantID, id)
	if err != nil {
		return Upload{}, err
	}
	if !exists {
		return Upload{}, ErrNotFound
	}
	return u, nil
}
