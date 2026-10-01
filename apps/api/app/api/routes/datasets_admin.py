"""Administrator trust layer: dataset registry, publication decisions, governed imports, audit trail."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_, select

from app.api.dependencies.auth import DbSession, require_csrf
from app.api.dependencies.platform_admin import require_platform_administrator
from app.api.routes.knowledge import reset_domains_cache
from app.models.content_contract import DataSet, DataSetImport, PlatformAuditEvent
from app.core.errors import ApplicationError
from app.models.identity import Session, User
from app.services.data_contracts import can_publish
from app.importers import ADAPTERS, get_adapter
from app.importers.runner import run_adapter
from app.services.data_quality import dataset_conflicts, quality_report
from app.services.datasets import MAX_RECORDS_PER_UPLOAD, DatasetService
from app.services.readiness import live_state, load_registry, summarise
from app.services.manifest import load_manifest, validate_manifest
from app.services.publication_policy import apply_manifest_policy
from app.services.verification import clear_cache as clear_verification_cache

router = APIRouter(prefix="/admin/datasets", tags=["admin-datasets"])
Admin = Annotated[User, Depends(require_platform_administrator)]
Csrf = Annotated[Session, Depends(require_csrf)]


def dataset_view(d: DataSet) -> dict:
    allowed, reasons = can_publish(license_status=d.license_status, validation_status=d.validation_status, rights_confirmation=d.rights_confirmation)
    return {"id": d.dataset_key, "name": d.name, "purpose": d.purpose, "type": d.entity_type, "source": {"name": d.source_name, "url": d.source_url, "version": d.version},
            "date_acquired": d.date_acquired.isoformat() if d.date_acquired else None, "license": {"name": d.license_name, "status": d.license_status},
            "provenance": d.provenance, "importer": d.importer, "importer_version": d.importer_version, "checksum_sha256": d.checksum_sha256,
            "validation_status": d.validation_status, "publication_status": d.publication_status, "enabled": d.enabled, "readiness": d.readiness,
            "rights_confirmation": d.rights_confirmation, "remaining_action": d.remaining_action, "record_count": d.record_count,
            "can_publish": allowed, "cannot_publish_because": list(reasons)}


@router.get("")
async def list_datasets(db: DbSession, _: Admin):
    return {"datasets": [dataset_view(d) for d in (await db.scalars(select(DataSet).order_by(DataSet.dataset_key))).all()]}


@router.get("/manifest/check")
async def manifest_check(_: Admin):
    manifest = load_manifest()
    return {"datasets": len(manifest["datasets"]), "problems": validate_manifest(manifest)}


@router.post("/manifest/sync")
async def manifest_sync(db: DbSession, admin: Admin, _: Csrf):
    """Register manifest datasets and re-apply every publication decision to the content tables."""
    manifest = load_manifest()
    problems = validate_manifest(manifest)
    if problems:
        return {"applied": False, "problems": problems}
    service = DatasetService(db)
    for entry in manifest["datasets"]:
        await service.register(entry, admin)
    await db.flush()
    report = await apply_manifest_policy(db, manifest)
    await service.audit(admin, "dataset.manifest_synced", "data_set", None, {"datasets": len(manifest["datasets"])})
    await db.commit()
    clear_verification_cache()
    reset_domains_cache()
    return {"applied": True, "report": report}


class ActionPayload(BaseModel):
    action: str = Field(pattern=r"^(publish|unpublish|stage|disable|enable|reject|mark_verified)$")
    note: str | None = Field(default=None, max_length=1000)
    confirmed_by: str | None = Field(default=None, max_length=200)
    confirmed_on: str | None = Field(default=None, max_length=40)
    basis: str | None = Field(default=None, max_length=1000)


@router.post("/{key}/action")
async def dataset_action(key: str, payload: ActionPayload, db: DbSession, admin: Admin, _: Csrf):
    """Publishing a dataset whose licence is not clearly open requires the owner's recorded rights confirmation."""
    confirmation = None
    if payload.confirmed_by or payload.confirmed_on or payload.basis:
        confirmation = {"confirmed_by": payload.confirmed_by or "", "confirmed_on": payload.confirmed_on or "", "basis": payload.basis or ""}
    service = DatasetService(db)
    dataset = await service.apply_action(key, payload.action, admin, note=payload.note, rights_confirmation=confirmation)
    await db.flush()
    await apply_manifest_policy(db, load_manifest())
    await db.commit()
    clear_verification_cache()
    reset_domains_cache()
    return dataset_view(dataset)


class UploadPayload(BaseModel):
    records: list[dict] = Field(min_length=1, max_length=MAX_RECORDS_PER_UPLOAD)
    allow_partial: bool = False  # default is all-or-nothing: one invalid row rejects the whole file


def import_view(imp: DataSetImport) -> dict:
    return {"id": str(imp.id), "status": imp.status, "created": imp.created_count, "updated": imp.updated_count, "unchanged": imp.unchanged_count,
            "failed": imp.failed_count, "failures": imp.failures, "file_sha256": imp.file_sha256, "importer_version": imp.importer_version,
            "adapter_id": imp.adapter_id, "source_version": imp.source_version, "source_checksum": imp.source_checksum,
            "source_retrieved_at": imp.source_retrieved_at.isoformat() if imp.source_retrieved_at else None, "at": imp.created_at.isoformat()}


@router.post("/{key}/preview")
async def preview_records(key: str, payload: UploadPayload, db: DbSession, _: Admin, __: Csrf):
    """Validate a knowledge-record file and show what an import would do, without writing anything."""
    return await DatasetService(db).preview_records(key, payload.records)


@router.post("/{key}/preview-listings")
async def preview_listings(key: str, payload: UploadPayload, db: DbSession, _: Admin, __: Csrf):
    return await DatasetService(db).preview_listings(key, payload.records)


@router.post("/{key}/import")
async def import_records(key: str, payload: UploadPayload, db: DbSession, admin: Admin, _: Csrf):
    imp = await DatasetService(db).import_records(key, payload.records, admin, strict=not payload.allow_partial)
    await db.commit()
    reset_domains_cache()
    return import_view(imp)


@router.post("/{key}/import-listings")
async def import_listings(key: str, payload: UploadPayload, db: DbSession, admin: Admin, _: Csrf):
    imp = await DatasetService(db).import_listings(key, payload.records, admin, strict=not payload.allow_partial)
    await db.commit()
    reset_domains_cache()
    return import_view(imp)


@router.get("/{key}/provenance")
async def provenance(key: str, db: DbSession, _: Admin):
    """Everything an administrator needs to judge a dataset: source, licence, provenance, rights decision, import history."""
    service = DatasetService(db)
    dataset = await service.by_key(key)
    rows = (await db.scalars(select(DataSetImport).where(DataSetImport.dataset_id == dataset.id).order_by(DataSetImport.created_at.desc()).limit(20))).all()
    import_ids = select(DataSetImport.id).where(DataSetImport.dataset_id == dataset.id)
    events = (await db.scalars(select(PlatformAuditEvent).where(or_(PlatformAuditEvent.target_id == dataset.id, PlatformAuditEvent.target_id.in_(import_ids)))
                               .order_by(PlatformAuditEvent.created_at.desc()).limit(50))).all()
    return {"dataset": dataset_view(dataset), "imports": [import_view(r) for r in rows],
            "events": [{"action": e.action, "at": e.created_at.isoformat(), "metadata": e.metadata_json} for e in events]}


@router.get("/{key}/imports")
async def imports(key: str, db: DbSession, _: Admin):
    dataset = await DatasetService(db).by_key(key)
    rows = (await db.scalars(select(DataSetImport).where(DataSetImport.dataset_id == dataset.id).order_by(DataSetImport.created_at.desc()).limit(50))).all()
    return {"imports": [import_view(r) for r in rows]}


@router.post("/imports/{import_id}/rollback")
async def rollback(import_id: UUID, db: DbSession, admin: Admin, _: Csrf):
    imp = await DatasetService(db).rollback_import(import_id, admin)
    await db.commit()
    reset_domains_cache()
    return import_view(imp)


@router.get("/audit/events")
async def audit_events(db: DbSession, _: Admin, limit: Annotated[int, Query(ge=1, le=200)] = 100, action: str | None = None):
    stmt = select(PlatformAuditEvent).order_by(PlatformAuditEvent.created_at.desc()).limit(limit)
    if action:
        stmt = stmt.where(PlatformAuditEvent.action.like(f"{action}%"))
    return {"events": [{"id": str(e.id), "action": e.action, "actor": str(e.actor_user_id) if e.actor_user_id else None, "target_type": e.target_type,
                        "target_id": str(e.target_id) if e.target_id else None, "metadata": e.metadata_json, "at": e.created_at.isoformat()} for e in (await db.scalars(stmt)).all()]}


# ------------------------------------------------------------------ readiness, quality, conflicts, importers
@router.get("/readiness")
async def readiness(db: DbSession, _: Admin):
    """Every domain with its status, the gates that fail and every blocker: exactly why it is not READY."""
    return summarise(load_registry(), await live_state(db))


@router.get("/quality-report")
async def quality(db: DbSession, _: Admin):
    return await quality_report(db)


@router.get("/{key}/conflicts")
async def conflicts(key: str, db: DbSession, _: Admin, limit: Annotated[int, Query(ge=1, le=500)] = 100):
    """Duplicate and conflict candidates for a dataset. Reported for review; nothing is merged, renamed or corrected."""
    await DatasetService(db).by_key(key)
    return await dataset_conflicts(db, key, limit)


@router.get("/importers/list")
async def importers(db: DbSession, _: Admin, probe: bool = False):
    """Registered source adapters with their last runs. `probe=true` checks whether each source is reachable from this server right now."""
    rows = []
    for adapter in ADAPTERS.values():
        dataset = await DatasetService(db).by_key(adapter.dataset_key)
        last = await db.scalar(select(DataSetImport).where(DataSetImport.dataset_id == dataset.id, DataSetImport.adapter_id == adapter.id).order_by(DataSetImport.created_at.desc()).limit(1))
        rows.append({**adapter.describe(), "last_run": import_view(last) if last else None, "dataset_publication": dataset.publication_status, "license_status": dataset.license_status,
                     "probe": adapter.probe() if probe else None})
    return {"importers": rows}


class RunPayload(BaseModel):
    params: dict[str, str] = Field(default_factory=dict)


@router.post("/importers/{adapter_id}/preview")
async def importer_preview(adapter_id: str, payload: RunPayload, db: DbSession, admin: Admin, _: Csrf):
    """Fetch and validate the source and show what an import would do. Writes nothing."""
    try:
        adapter = get_adapter(adapter_id)
        result = await run_adapter(db, adapter, payload.params, apply=False, actor=admin)
    except (KeyError, ValueError) as exc:
        raise ApplicationError("importer_invalid", str(exc), 422) from exc
    except Exception as exc:  # network or upstream failure: reported, never partially applied
        raise ApplicationError("importer_unavailable", f"The source could not be retrieved: {exc.__class__.__name__}: {exc}", 502) from exc
    return result


@router.post("/importers/{adapter_id}/run")
async def importer_run(adapter_id: str, payload: RunPayload, db: DbSession, admin: Admin, _: Csrf):
    """Run an importer all-or-nothing. Re-running an unchanged source changes nothing. Never publishes."""
    try:
        adapter = get_adapter(adapter_id)
        result = await run_adapter(db, adapter, payload.params, apply=True, actor=admin)
    except (KeyError, ValueError) as exc:
        raise ApplicationError("importer_invalid", str(exc), 422) from exc
    except ApplicationError:
        raise
    except Exception as exc:
        await db.rollback()
        raise ApplicationError("importer_unavailable", f"The source could not be retrieved: {exc.__class__.__name__}: {exc}", 502) from exc
    await db.commit()
    reset_domains_cache()
    return result
