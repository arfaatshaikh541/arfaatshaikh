// Package artefacts implements the server-authorised object-storage upload/
// download workflow for workload and model artefacts (approved
// architecture's Milestone 4 scope). control-api never proxies object
// bytes and never hands out storage credentials -- it only issues
// short-lived presigned URLs, records who was given one and when
// (artefact_access_grants), and independently verifies with the storage
// backend that an upload actually completed before ever treating an
// artefact as usable.
package artefacts

import (
	"time"

	"github.com/google/uuid"
)

type Upload struct {
	ID                uuid.UUID      `json:"id"`
	TenantID          uuid.UUID      `json:"enterprise_tenant_id"`
	OperatorID        *uuid.UUID     `json:"operator_id,omitempty"`
	ObjectKey         string         `json:"object_key"`
	Bucket            string         `json:"bucket"`
	Purpose           string         `json:"purpose"`
	ContentType       string         `json:"content_type"`
	ContentLength     *int64         `json:"content_length,omitempty"`
	ChecksumSHA256    *string        `json:"checksum_sha256,omitempty"`
	Status            string         `json:"status"`
	MalwareScanStatus string         `json:"malware_scan_status"`
	VersionID         *string        `json:"version_id,omitempty"`
	RetentionPolicy   map[string]any `json:"retention_policy"`
	UploadedBy        uuid.UUID      `json:"uploaded_by"`
	UploadedAt        *time.Time     `json:"uploaded_at,omitempty"`
	DeletedBy         *uuid.UUID     `json:"deleted_by,omitempty"`
	DeletedAt         *time.Time     `json:"deleted_at,omitempty"`
	CreatedAt         time.Time      `json:"created_at"`
	UpdatedAt         time.Time      `json:"updated_at"`
}

type AccessGrant struct {
	ID        uuid.UUID  `json:"id"`
	TenantID  uuid.UUID  `json:"enterprise_tenant_id"`
	UploadID  uuid.UUID  `json:"artefact_upload_id"`
	GrantedTo uuid.UUID  `json:"granted_to"`
	Action    string     `json:"action"`
	ExpiresAt time.Time  `json:"expires_at"`
	UsedAt    *time.Time `json:"used_at,omitempty"`
	CreatedAt time.Time  `json:"created_at"`
}
