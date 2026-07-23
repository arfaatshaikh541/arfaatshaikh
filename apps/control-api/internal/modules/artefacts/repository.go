package artefacts

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
)

type conn interface {
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
}

const uploadColumns = `
	id, enterprise_tenant_id, operator_id, object_key, bucket, purpose, content_type,
	content_length, checksum_sha256, status, malware_scan_status, version_id,
	retention_policy, uploaded_by, uploaded_at, deleted_by, deleted_at, created_at, updated_at
`

func scanUpload(row pgx.Row) (Upload, error) {
	var u Upload
	var retentionRaw []byte
	err := row.Scan(
		&u.ID, &u.TenantID, &u.OperatorID, &u.ObjectKey, &u.Bucket, &u.Purpose, &u.ContentType,
		&u.ContentLength, &u.ChecksumSHA256, &u.Status, &u.MalwareScanStatus, &u.VersionID,
		&retentionRaw, &u.UploadedBy, &u.UploadedAt, &u.DeletedBy, &u.DeletedAt, &u.CreatedAt, &u.UpdatedAt,
	)
	if err != nil {
		return Upload{}, err
	}
	if err := json.Unmarshal(retentionRaw, &u.RetentionPolicy); err != nil {
		return Upload{}, fmt.Errorf("unmarshal retention policy: %w", err)
	}
	return u, nil
}

func createUpload(ctx context.Context, c conn, tenantID uuid.UUID, operatorID *uuid.UUID, objectKey, bucket, purpose, contentType string, contentLength int64, uploadedBy uuid.UUID, retentionPolicy map[string]any) (Upload, error) {
	retentionJSON, err := json.Marshal(retentionPolicy)
	if err != nil {
		return Upload{}, fmt.Errorf("marshal retention policy: %w", err)
	}
	row := c.QueryRow(ctx, `
		INSERT INTO artefact_uploads (
			enterprise_tenant_id, operator_id, object_key, bucket, purpose, content_type,
			content_length, status, uploaded_by, retention_policy
		)
		VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending', $8, $9)
		RETURNING `+uploadColumns,
		tenantID, operatorID, objectKey, bucket, purpose, contentType, contentLength, uploadedBy, retentionJSON,
	)
	u, err := scanUpload(row)
	if err != nil {
		return Upload{}, fmt.Errorf("insert artefact upload: %w", err)
	}
	return u, nil
}

func getUploadByID(ctx context.Context, c conn, tenantID, id uuid.UUID) (Upload, bool, error) {
	row := c.QueryRow(ctx, `
		SELECT `+uploadColumns+`
		FROM artefact_uploads WHERE enterprise_tenant_id = $1 AND id = $2
	`, tenantID, id)
	u, err := scanUpload(row)
	if err != nil {
		if err == pgx.ErrNoRows {
			return Upload{}, false, nil
		}
		return Upload{}, false, fmt.Errorf("get artefact upload: %w", err)
	}
	return u, true, nil
}

func listUploads(ctx context.Context, c conn, tenantID uuid.UUID) ([]Upload, error) {
	rows, err := c.Query(ctx, `
		SELECT `+uploadColumns+`
		FROM artefact_uploads WHERE enterprise_tenant_id = $1 ORDER BY created_at DESC
	`, tenantID)
	if err != nil {
		return nil, fmt.Errorf("list artefact uploads: %w", err)
	}
	defer rows.Close()
	return scanUploads(rows)
}

func scanUploads(rows pgx.Rows) ([]Upload, error) {
	uploads := []Upload{}
	for rows.Next() {
		u, err := scanUpload(rows)
		if err != nil {
			return nil, fmt.Errorf("scan artefact upload: %w", err)
		}
		uploads = append(uploads, u)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	return uploads, nil
}

func markUploaded(ctx context.Context, c conn, id uuid.UUID, contentLength int64, checksum, versionID string) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE artefact_uploads
		SET status = 'uploaded', content_length = $2, checksum_sha256 = $3, version_id = $4,
		    uploaded_at = now(), updated_at = now()
		WHERE id = $1 AND status = 'pending'
	`, id, contentLength, checksum, versionID)
	if err != nil {
		return false, fmt.Errorf("mark artefact uploaded: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

func markFailed(ctx context.Context, c conn, id uuid.UUID) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE artefact_uploads SET status = 'failed', updated_at = now()
		WHERE id = $1 AND status = 'pending'
	`, id)
	if err != nil {
		return false, fmt.Errorf("mark artefact failed: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

func markDeleted(ctx context.Context, c conn, id, deletedBy uuid.UUID) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE artefact_uploads SET status = 'deleted', deleted_by = $2, deleted_at = now(), updated_at = now()
		WHERE id = $1 AND status <> 'deleted'
	`, id, deletedBy)
	if err != nil {
		return false, fmt.Errorf("mark artefact deleted: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

func setMalwareScanStatus(ctx context.Context, c conn, id uuid.UUID, status string) (bool, error) {
	tag, err := c.Exec(ctx, `
		UPDATE artefact_uploads SET malware_scan_status = $2, updated_at = now()
		WHERE id = $1
	`, id, status)
	if err != nil {
		return false, fmt.Errorf("set malware scan status: %w", err)
	}
	return tag.RowsAffected() > 0, nil
}

func createAccessGrant(ctx context.Context, c conn, tenantID, uploadID, grantedTo uuid.UUID, action string, expiresAt any) error {
	_, err := c.Exec(ctx, `
		INSERT INTO artefact_access_grants (enterprise_tenant_id, artefact_upload_id, granted_to, action, expires_at)
		VALUES ($1, $2, $3, $4, $5)
	`, tenantID, uploadID, grantedTo, action, expiresAt)
	if err != nil {
		return fmt.Errorf("insert artefact access grant: %w", err)
	}
	return nil
}
