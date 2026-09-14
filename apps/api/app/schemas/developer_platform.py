from pydantic import BaseModel, Field


class CredentialPolicyRequest(BaseModel):
    key_prefix: str
    secret_hash: str
    scopes: set[str]
    rate_limit_per_minute: int = Field(ge=1, le=6000)
    application_status: str


class WebhookEndpointRequest(BaseModel):
    endpoint_url: str
    subscribed_events: set[str]


class WebhookSignatureRequest(BaseModel):
    payload: str
    timestamp: str
    signature_hex: str
    secret: str = Field(min_length=16)


class DeliveryRetryRequest(BaseModel):
    status_code: int | None = Field(default=None, ge=100, le=599)
    attempt_count: int = Field(ge=0, le=12)


class AccessPolicyRequest(BaseModel):
    application_status: str
    credential_status: str
    granted_scopes: set[str]
    required_scope: str
    tenant_matches: bool
    credential_expired: bool = False
    rate_limit_remaining: int


class QuotaPolicyRequest(BaseModel):
    current_count: int = Field(ge=0)
    limit_count: int = Field(gt=0)
    requested_units: int = Field(default=1, gt=0)


class UsageRecordRequest(BaseModel):
    idempotency_key: str
    request_id: str
    route_template: str
    billable_units: int = Field(default=1, ge=0, le=10000)


class AuditEvidenceRequest(BaseModel):
    evidence_sha256: str
    event_type: str
    summary: str

class APIVersionPolicyRequest(BaseModel):
    version: str
    lifecycle_status: str
    specification_sha256: str
    breaking_changes: list[str] = []
    sunset_notice_days: int = Field(ge=0)
    successor_version: str | None = None


class DocumentationArtifactRequest(BaseModel):
    artifact_type: str
    locale: str = "en"
    content_uri: str
    content_sha256: str
    verified: bool


class SDKReleasePolicyRequest(BaseModel):
    language: str
    version: str
    package_uri: str
    package_sha256: str
    tests_passed: bool
    provenance_verified: bool
    api_version_status: str


class SandboxSessionPolicyRequest(BaseModel):
    application_status: str
    requested_scopes: set[str]
    request_limit: int = Field(ge=1, le=1000)
    used_requests: int = Field(ge=0)
    expired: bool = False

class PartnerApplicationPolicyRequest(BaseModel):
    website_url: str
    privacy_contact: str
    terms_accepted: bool
    organisation_active: bool


class IntegrationListingPolicyRequest(BaseModel):
    slug: str
    partner_status: str
    application_status: str
    requested_scopes: set[str]
    support_url: str
    security_review_passed: bool
    certification_active: bool


class IntegrationSecurityReviewPolicyRequest(BaseModel):
    evidence_sha256: str
    critical_findings: int = Field(ge=0)
    high_findings: int = Field(ge=0)
    data_minimisation_verified: bool
    deletion_verified: bool
    independent_reviewer: bool


class IntegrationCertificationPolicyRequest(BaseModel):
    certificate_version: str
    certification_sha256: str
    security_review_passed: bool
    expires_in_days: int = Field(ge=0)
    partner_status: str


class PartnerIncidentPolicyRequest(BaseModel):
    severity: str
    status: str
    credentials_revoked: bool
    listing_suspended: bool
    evidence_sha256: str

class SyncNodePolicyRequest(BaseModel):
    slug: str
    base_url: str
    public_key_fingerprint: str
    organisation_active: bool
    independent_verification: bool

class SyncTrustPolicyRequest(BaseModel):
    node_status: str
    direction: str
    content_types: set[str]
    require_signature: bool = True
    require_scholarly_approval: bool = True
    max_items_per_run: int = Field(ge=1, le=10000)

class SyncManifestPolicyRequest(BaseModel):
    manifest_sha256: str
    item_count: int = Field(ge=0, le=10000)
    checkpoint: str | None = None
    request_id: str
    replayed_request_ids: set[str] = set()

class SyncItemPolicyRequest(BaseModel):
    content_type: str
    payload_sha256: str
    signature_valid: bool
    content_version: str
    scholarly_approved: bool
    local_payload_sha256: str | None = None

class SyncConflictPolicyRequest(BaseModel):
    local_version: str
    remote_version: str
    local_sha256: str
    remote_sha256: str
    remote_scholarly_approved: bool
    manual_override: str | None = None

class SyncAuditHashRequest(BaseModel):
    run_id: str
    sequence_number: int = Field(ge=1)
    event_type: str
    evidence_sha256: str
    previous_event_sha256: str | None = None
    metadata: dict[str, object] = {}

class SyncSchedulePolicyRequest(BaseModel):
    node_status: str
    direction: str
    interval_minutes: int = Field(ge=1)
    max_concurrent_runs: int = Field(ge=1)
    jitter_seconds: int = Field(ge=0)

class SyncChunkPlanRequest(BaseModel):
    total_items: int = Field(ge=0)
    total_bytes: int = Field(ge=0)
    max_items_per_chunk: int = Field(ge=1)
    max_bytes_per_chunk: int = Field(ge=1)

class SyncChunkPolicyRequest(BaseModel):
    payload_sha256: str
    compressed_sha256: str | None = None
    byte_count: int = Field(ge=0)
    item_count: int = Field(ge=0)
    idempotency_key: str
    replayed_keys: set[str] = set()

class SyncTransferRetryRequest(BaseModel):
    attempt_count: int = Field(ge=0, le=8)
    response_status: int | None = Field(default=None, ge=100, le=599)
    network_error: bool = False
    cancelled: bool = False

class SyncBatchReconcileRequest(BaseModel):
    total_chunks: int = Field(ge=0)
    verified_chunks: int = Field(ge=0)
    failed_chunks: int = Field(ge=0)
    cancelled_chunks: int = Field(default=0, ge=0)

class SyncCheckpointAdvanceRequest(BaseModel):
    current_checkpoint: str | None = None
    proposed_checkpoint: str | None = None
    batch_status: str
    unresolved_conflicts: int = Field(ge=0)
    dead_letters: int = Field(ge=0)

class SyncChunkIdempotencyRequest(BaseModel):
    run_id: str
    batch_number: int = Field(ge=1)
    chunk_number: int = Field(ge=1)
    payload_sha256: str

class SyncPartitionDigestRequest(BaseModel):
    partition_key: str
    ordered_items: list[dict[str, str]]

class SyncSnapshotRootRequest(BaseModel):
    content_type: str
    snapshot_version: str
    partition_digests: list[dict[str, str]]

class SyncSnapshotSealRequest(BaseModel):
    node_status: str
    content_type: str
    root_sha256: str
    item_count: int = Field(ge=0)
    partition_count: int = Field(ge=0)
    calculated_partition_count: int = Field(ge=0)

class SyncSnapshotCompareRequest(BaseModel):
    local_root_sha256: str
    remote_root_sha256: str
    local_partitions: dict[str, str]
    remote_partitions: dict[str, str]

class SyncRepairPlanRequest(BaseModel):
    content_type: str
    strategy: str
    partition_keys: list[str]
    drift_status: str
    scholarly_approved: bool = False
    automatic_replacement: bool = False

class SyncIntegrityVerifyRequest(BaseModel):
    expected_root_sha256: str
    calculated_root_sha256: str
    expected_partitions: int = Field(ge=0)
    verified_partitions: int = Field(ge=0)
    unresolved_drift: int = Field(ge=0)

class SyncPeerAttestationRequest(BaseModel):
    node_status: str
    evidence_sha256: str
    independent_reviewer: bool
    expires_in_days: int = Field(ge=0)
    organisation_active: bool

class SyncPolicyChangeRequest(BaseModel):
    content_types: set[str]
    expands_access: bool
    requestor_is_approver: bool
    change_ticket: str
    evidence_sha256: str
    rollback_defined: bool

class SyncSecurityIncidentRequest(BaseModel):
    severity: str
    status: str
    evidence_sha256: str
    node_suspended: bool
    credentials_revoked: bool
    transfers_cancelled: bool

class SyncQuarantineReleaseRequest(BaseModel):
    incident_status: str
    release_evidence_sha256: str
    integrity_verification_passed: bool
    credentials_rotated: bool
    independent_approval: bool
    unresolved_drift: int = Field(ge=0)

class SyncFederationAcceptanceRequest(BaseModel):
    open_high_incidents: int = Field(ge=0)
    open_critical_incidents: int = Field(ge=0)
    integrity_gate_passed: bool
    replay_protection_tested: bool
    recovery_rehearsal_passed: bool
    audit_chain_verified: bool
    scholarly_governance_verified: bool
    live_network_tested: bool = False
