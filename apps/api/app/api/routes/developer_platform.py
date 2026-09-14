from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies.auth import get_current_user
from app.models.identity import User
from app.schemas.developer_platform import CredentialPolicyRequest, DeliveryRetryRequest, WebhookEndpointRequest, WebhookSignatureRequest
from app.services.developer_platform import CredentialPolicyInput, evaluate_credential_policy, evaluate_delivery_retry, validate_webhook_endpoint, verify_webhook_signature

router = APIRouter(prefix="/developer-platform", tags=["developer-platform"])


@router.post("/credentials/evaluate")
async def credential_evaluate(payload: CredentialPolicyRequest, _: Annotated[User, Depends(get_current_user)]):
    return evaluate_credential_policy(CredentialPolicyInput(**payload.model_dump()))


@router.post("/webhooks/endpoints/validate")
async def webhook_endpoint_validate(payload: WebhookEndpointRequest, _: Annotated[User, Depends(get_current_user)]):
    return validate_webhook_endpoint(payload.endpoint_url, payload.subscribed_events)


@router.post("/webhooks/signatures/verify")
async def webhook_signature_verify(payload: WebhookSignatureRequest, _: Annotated[User, Depends(get_current_user)]):
    return verify_webhook_signature(payload=payload.payload.encode("utf-8"), timestamp=payload.timestamp, signature_hex=payload.signature_hex, secret=payload.secret)


@router.post("/webhooks/deliveries/retry-policy")
async def delivery_retry_policy(payload: DeliveryRetryRequest, _: Annotated[User, Depends(get_current_user)]):
    try:
        return evaluate_delivery_retry(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

from app.schemas.developer_platform import AccessPolicyRequest, AuditEvidenceRequest, QuotaPolicyRequest, UsageRecordRequest
from app.services.developer_access import AccessRequest, evaluate_api_access, evaluate_quota, validate_audit_evidence, validate_usage_record


@router.post("/access/evaluate")
async def access_evaluate(payload: AccessPolicyRequest, _: Annotated[User, Depends(get_current_user)]):
    return evaluate_api_access(AccessRequest(**payload.model_dump()))


@router.post("/quotas/evaluate")
async def quota_evaluate(payload: QuotaPolicyRequest, _: Annotated[User, Depends(get_current_user)]):
    try:
        return evaluate_quota(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/usage/validate")
async def usage_validate(payload: UsageRecordRequest, _: Annotated[User, Depends(get_current_user)]):
    return validate_usage_record(**payload.model_dump())


@router.post("/audit-evidence/validate")
async def audit_evidence_validate(payload: AuditEvidenceRequest, _: Annotated[User, Depends(get_current_user)]):
    return validate_audit_evidence(**payload.model_dump())

from app.schemas.developer_platform import APIVersionPolicyRequest, DocumentationArtifactRequest, SDKReleasePolicyRequest, SandboxSessionPolicyRequest
from app.services.developer_ecosystem import evaluate_api_version, evaluate_sdk_release, evaluate_sandbox_session, validate_documentation_artifact


@router.post("/versions/evaluate")
async def version_evaluate(payload: APIVersionPolicyRequest, _: Annotated[User, Depends(get_current_user)]):
    return evaluate_api_version(**payload.model_dump())


@router.post("/documentation/validate")
async def documentation_validate(payload: DocumentationArtifactRequest, _: Annotated[User, Depends(get_current_user)]):
    return validate_documentation_artifact(**payload.model_dump())


@router.post("/sdks/evaluate")
async def sdk_evaluate(payload: SDKReleasePolicyRequest, _: Annotated[User, Depends(get_current_user)]):
    return evaluate_sdk_release(**payload.model_dump())


@router.post("/sandbox/evaluate")
async def sandbox_evaluate(payload: SandboxSessionPolicyRequest, _: Annotated[User, Depends(get_current_user)]):
    return evaluate_sandbox_session(**payload.model_dump())

from app.schemas.developer_platform import IntegrationCertificationPolicyRequest, IntegrationListingPolicyRequest, IntegrationSecurityReviewPolicyRequest, PartnerApplicationPolicyRequest, PartnerIncidentPolicyRequest
from app.services.developer_partners import evaluate_certification, evaluate_integration_listing, evaluate_partner_application, evaluate_partner_incident, evaluate_security_review


@router.post("/partners/evaluate")
async def partner_evaluate(payload: PartnerApplicationPolicyRequest, _: Annotated[User, Depends(get_current_user)]):
    return evaluate_partner_application(**payload.model_dump())


@router.post("/integrations/evaluate")
async def integration_evaluate(payload: IntegrationListingPolicyRequest, _: Annotated[User, Depends(get_current_user)]):
    return evaluate_integration_listing(**payload.model_dump())


@router.post("/integrations/security-review/evaluate")
async def integration_security_review_evaluate(payload: IntegrationSecurityReviewPolicyRequest, _: Annotated[User, Depends(get_current_user)]):
    return evaluate_security_review(**payload.model_dump())


@router.post("/integrations/certification/evaluate")
async def integration_certification_evaluate(payload: IntegrationCertificationPolicyRequest, _: Annotated[User, Depends(get_current_user)]):
    return evaluate_certification(**payload.model_dump())


@router.post("/partners/incidents/evaluate")
async def partner_incident_evaluate(payload: PartnerIncidentPolicyRequest, _: Annotated[User, Depends(get_current_user)]):
    return evaluate_partner_incident(**payload.model_dump())

from app.schemas.developer_platform import SyncAuditHashRequest, SyncConflictPolicyRequest, SyncItemPolicyRequest, SyncManifestPolicyRequest, SyncNodePolicyRequest, SyncTrustPolicyRequest
from app.services.knowledge_sync import compute_audit_event_hash, evaluate_sync_item, evaluate_sync_node, evaluate_trust_policy, resolve_conflict, validate_manifest

@router.post("/synchronization/nodes/evaluate")
async def synchronization_node_evaluate(payload: SyncNodePolicyRequest, _: Annotated[User, Depends(get_current_user)]):
    return evaluate_sync_node(**payload.model_dump())

@router.post("/synchronization/trust-policies/evaluate")
async def synchronization_trust_policy_evaluate(payload: SyncTrustPolicyRequest, _: Annotated[User, Depends(get_current_user)]):
    return evaluate_trust_policy(**payload.model_dump())

@router.post("/synchronization/manifests/validate")
async def synchronization_manifest_validate(payload: SyncManifestPolicyRequest, _: Annotated[User, Depends(get_current_user)]):
    return validate_manifest(**payload.model_dump())

@router.post("/synchronization/items/evaluate")
async def synchronization_item_evaluate(payload: SyncItemPolicyRequest, _: Annotated[User, Depends(get_current_user)]):
    return evaluate_sync_item(**payload.model_dump())

@router.post("/synchronization/conflicts/resolve")
async def synchronization_conflict_resolve(payload: SyncConflictPolicyRequest, _: Annotated[User, Depends(get_current_user)]):
    try:
        return resolve_conflict(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.post("/synchronization/audit-events/hash")
async def synchronization_audit_hash(payload: SyncAuditHashRequest, _: Annotated[User, Depends(get_current_user)]):
    try:
        return {"event_sha256": compute_audit_event_hash(**payload.model_dump())}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

from app.schemas.developer_platform import SyncBatchReconcileRequest, SyncCheckpointAdvanceRequest, SyncChunkIdempotencyRequest, SyncChunkPlanRequest, SyncChunkPolicyRequest, SyncSchedulePolicyRequest, SyncTransferRetryRequest
from app.services.knowledge_sync_transport import compute_chunk_idempotency_key, evaluate_checkpoint_advance, evaluate_chunk, evaluate_schedule, evaluate_transfer_retry, plan_transfer_chunks, reconcile_batch

@router.post("/synchronization/schedules/evaluate")
async def synchronization_schedule_evaluate(payload: SyncSchedulePolicyRequest, _: Annotated[User, Depends(get_current_user)]):
    return evaluate_schedule(**payload.model_dump())

@router.post("/synchronization/chunks/plan")
async def synchronization_chunk_plan(payload: SyncChunkPlanRequest, _: Annotated[User, Depends(get_current_user)]):
    try:
        return plan_transfer_chunks(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.post("/synchronization/chunks/evaluate")
async def synchronization_chunk_evaluate(payload: SyncChunkPolicyRequest, _: Annotated[User, Depends(get_current_user)]):
    return evaluate_chunk(**payload.model_dump())

@router.post("/synchronization/transfers/retry-policy")
async def synchronization_transfer_retry(payload: SyncTransferRetryRequest, _: Annotated[User, Depends(get_current_user)]):
    try:
        return evaluate_transfer_retry(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.post("/synchronization/batches/reconcile")
async def synchronization_batch_reconcile(payload: SyncBatchReconcileRequest, _: Annotated[User, Depends(get_current_user)]):
    try:
        return reconcile_batch(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.post("/synchronization/checkpoints/evaluate")
async def synchronization_checkpoint_evaluate(payload: SyncCheckpointAdvanceRequest, _: Annotated[User, Depends(get_current_user)]):
    return evaluate_checkpoint_advance(**payload.model_dump())

@router.post("/synchronization/chunks/idempotency-key")
async def synchronization_chunk_idempotency(payload: SyncChunkIdempotencyRequest, _: Annotated[User, Depends(get_current_user)]):
    try:
        return {"idempotency_key": compute_chunk_idempotency_key(**payload.model_dump())}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

from app.schemas.developer_platform import SyncIntegrityVerifyRequest, SyncPartitionDigestRequest, SyncRepairPlanRequest, SyncSnapshotCompareRequest, SyncSnapshotRootRequest, SyncSnapshotSealRequest
from app.services.knowledge_sync_integrity import compare_snapshots, compute_partition_digest, compute_snapshot_root, evaluate_repair_plan, evaluate_snapshot_seal, verify_snapshot_integrity


@router.post("/synchronization/integrity/partitions/hash")
async def sync_partition_hash(payload: SyncPartitionDigestRequest, _: Annotated[User, Depends(get_current_user)]):
    try:
        return {"digest_sha256": compute_partition_digest(**payload.model_dump())}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/synchronization/integrity/snapshots/root")
async def sync_snapshot_root(payload: SyncSnapshotRootRequest, _: Annotated[User, Depends(get_current_user)]):
    try:
        return {"root_sha256": compute_snapshot_root(**payload.model_dump())}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/synchronization/integrity/snapshots/seal")
async def sync_snapshot_seal(payload: SyncSnapshotSealRequest, _: Annotated[User, Depends(get_current_user)]):
    return evaluate_snapshot_seal(**payload.model_dump())


@router.post("/synchronization/integrity/snapshots/compare")
async def sync_snapshot_compare(payload: SyncSnapshotCompareRequest, _: Annotated[User, Depends(get_current_user)]):
    try:
        return compare_snapshots(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/synchronization/integrity/repairs/evaluate")
async def sync_repair_evaluate(payload: SyncRepairPlanRequest, _: Annotated[User, Depends(get_current_user)]):
    return evaluate_repair_plan(**payload.model_dump())


@router.post("/synchronization/integrity/verify")
async def sync_integrity_verify(payload: SyncIntegrityVerifyRequest, _: Annotated[User, Depends(get_current_user)]):
    return verify_snapshot_integrity(**payload.model_dump())

from app.schemas.developer_platform import SyncFederationAcceptanceRequest, SyncPeerAttestationRequest, SyncPolicyChangeRequest, SyncQuarantineReleaseRequest, SyncSecurityIncidentRequest
from app.services.knowledge_sync_governance import evaluate_federation_acceptance, evaluate_peer_attestation, evaluate_policy_change, evaluate_quarantine_release, evaluate_security_incident

@router.post("/synchronization/governance/peer-attestations/evaluate")
async def sync_peer_attestation_evaluate(payload: SyncPeerAttestationRequest, _: Annotated[User, Depends(get_current_user)]):
    return evaluate_peer_attestation(**payload.model_dump())

@router.post("/synchronization/governance/policy-changes/evaluate")
async def sync_policy_change_evaluate(payload: SyncPolicyChangeRequest, _: Annotated[User, Depends(get_current_user)]):
    return evaluate_policy_change(**payload.model_dump())

@router.post("/synchronization/governance/incidents/evaluate")
async def sync_security_incident_evaluate(payload: SyncSecurityIncidentRequest, _: Annotated[User, Depends(get_current_user)]):
    try:
        return evaluate_security_incident(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.post("/synchronization/governance/quarantines/release")
async def sync_quarantine_release_evaluate(payload: SyncQuarantineReleaseRequest, _: Annotated[User, Depends(get_current_user)]):
    return evaluate_quarantine_release(**payload.model_dump())

@router.post("/synchronization/governance/acceptance/evaluate")
async def sync_federation_acceptance_evaluate(payload: SyncFederationAcceptanceRequest, _: Annotated[User, Depends(get_current_user)]):
    return evaluate_federation_acceptance(**payload.model_dump())
