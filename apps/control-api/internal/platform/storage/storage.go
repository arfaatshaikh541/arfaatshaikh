// Package storage wraps the S3-compatible object store (MinIO locally) used
// for workload/model artefacts. It never exposes storage credentials to a
// browser: every caller gets a short-lived, server-issued presigned URL for
// exactly one object and one operation (PUT or GET), never the underlying
// access key/secret. Object keys are always generated server-side by
// ObjectKey -- callers never choose their own path -- so every key is both
// non-guessable (a random UUID segment) and structurally isolated by
// enterprise tenant (and, where applicable, operator).
package storage

import (
	"context"
	"fmt"
	"io"
	"time"

	"github.com/google/uuid"
	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
)

type Client struct {
	mc     *minio.Client
	bucket string
}

// Bucket returns the bucket this client is configured to operate against.
func (c *Client) Bucket() string {
	return c.bucket
}

type Config struct {
	Endpoint  string
	AccessKey string
	SecretKey string
	UseSSL    bool
	Bucket    string
}

// Connect opens the MinIO/S3 client and ensures the configured bucket
// exists with object versioning enabled (so a later artefact upload can
// never silently clobber an earlier one at the same key -- see
// ObjectVersionID). Bucket creation/versioning is idempotent: running this
// against an already-provisioned bucket is a no-op.
func Connect(ctx context.Context, cfg Config) (*Client, error) {
	mc, err := minio.New(cfg.Endpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(cfg.AccessKey, cfg.SecretKey, ""),
		Secure: cfg.UseSSL,
	})
	if err != nil {
		return nil, fmt.Errorf("create storage client: %w", err)
	}

	exists, err := mc.BucketExists(ctx, cfg.Bucket)
	if err != nil {
		return nil, fmt.Errorf("check bucket exists: %w", err)
	}
	if !exists {
		if err := mc.MakeBucket(ctx, cfg.Bucket, minio.MakeBucketOptions{}); err != nil {
			return nil, fmt.Errorf("create bucket: %w", err)
		}
	}
	if err := mc.SetBucketVersioning(ctx, cfg.Bucket, minio.BucketVersioningConfiguration{Status: minio.Enabled}); err != nil {
		return nil, fmt.Errorf("enable bucket versioning: %w", err)
	}

	return &Client{mc: mc, bucket: cfg.Bucket}, nil
}

// ObjectKey builds a non-guessable, tenant-isolated (and, when operatorID is
// non-nil, additionally operator-isolated) object key. The random UUID
// segment is generated here, server-side -- never accepted from a client --
// so no caller can predict or collide with another tenant's/operator's
// object path.
func ObjectKey(tenantID uuid.UUID, operatorID *uuid.UUID) string {
	if operatorID != nil {
		return fmt.Sprintf("tenants/%s/operators/%s/%s", tenantID, operatorID, uuid.New())
	}
	return fmt.Sprintf("tenants/%s/%s", tenantID, uuid.New())
}

// PresignedPutURL returns a short-lived URL the caller's browser/CLI can PUT
// the object's bytes to directly -- control-api never proxies the upload
// body itself, and never hands out the underlying storage credentials.
func (c *Client) PresignedPutURL(ctx context.Context, objectKey string, expiry time.Duration) (string, error) {
	u, err := c.mc.PresignedPutObject(ctx, c.bucket, objectKey, expiry)
	if err != nil {
		return "", fmt.Errorf("presign put url: %w", err)
	}
	return u.String(), nil
}

// PresignedGetURL returns a short-lived download URL for exactly one object.
func (c *Client) PresignedGetURL(ctx context.Context, objectKey string, expiry time.Duration) (string, error) {
	u, err := c.mc.PresignedGetObject(ctx, c.bucket, objectKey, expiry, nil)
	if err != nil {
		return "", fmt.Errorf("presign get url: %w", err)
	}
	return u.String(), nil
}

type ObjectInfo struct {
	Size        int64
	ContentType string
	ETag        string
	VersionID   string
}

// Stat verifies an object actually exists in the backend (used to confirm
// upload completion -- an artefact is never marked "uploaded" on the
// client's say-so alone) and returns its observed size/content-type/etag/
// version, so the caller can compare them against what was declared at
// upload-authorisation time.
func (c *Client) Stat(ctx context.Context, objectKey string) (ObjectInfo, error) {
	info, err := c.mc.StatObject(ctx, c.bucket, objectKey, minio.StatObjectOptions{})
	if err != nil {
		return ObjectInfo{}, fmt.Errorf("stat object: %w", err)
	}
	return ObjectInfo{
		Size:        info.Size,
		ContentType: info.ContentType,
		ETag:        info.ETag,
		VersionID:   info.VersionID,
	}, nil
}

// Get opens a server-side read stream of an object -- used only for
// completion-time checksum verification (internal/modules/artefacts hashes
// the bytes itself rather than trusting a client-declared checksum), never
// to proxy a download to a browser (PresignedGetURL is what browsers use).
func (c *Client) Get(ctx context.Context, objectKey string) (io.ReadCloser, error) {
	obj, err := c.mc.GetObject(ctx, c.bucket, objectKey, minio.GetObjectOptions{})
	if err != nil {
		return nil, fmt.Errorf("get object: %w", err)
	}
	return obj, nil
}

// Remove deletes an object (all versions are retained by the bucket's
// versioning configuration unless the caller also removes those version IDs
// explicitly -- this call only removes the current/latest version, which is
// the deliberate "soft delete" behavior a versioned bucket gives us for
// free: a deletion/retirement workflow can still recover prior bytes).
func (c *Client) Remove(ctx context.Context, objectKey string) error {
	if err := c.mc.RemoveObject(ctx, c.bucket, objectKey, minio.RemoveObjectOptions{}); err != nil {
		return fmt.Errorf("remove object: %w", err)
	}
	return nil
}
