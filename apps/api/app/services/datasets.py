"""Dataset registry, governed imports and administrative actions. Every state change writes an AuditEvent."""
from __future__ import annotations

import hashlib
import json
from typing import Sequence
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApplicationError
from app.models.content_contract import DataSet, DataSetImport, DirectoryListing, KnowledgeRecord, PlatformAuditEvent
from app.models.identity import User
from app.services.data_contracts import IMPORTER_VERSION, DirectoryListingInput, can_publish, validate_record_batch

MAX_RECORDS_PER_UPLOAD = 5000
MAX_ERRORS_REPORTED = 200

ACTIONS = {"publish", "unpublish", "stage", "disable", "enable", "reject", "mark_verified"}


def sha256_json(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


class DatasetService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def audit(self, actor: User | None, action: str, target_type: str, target_id: UUID | None, meta: dict) -> None:
        self.session.add(PlatformAuditEvent(
            actor_user_id=actor.id if actor else None, action=action, target_type=target_type, target_id=target_id,
            metadata_json=json.loads(json.dumps(meta, default=str, ensure_ascii=False)), created_at=datetime.now(UTC)))

    async def by_key(self, key: str) -> DataSet:
        dataset = await self.session.scalar(select(DataSet).where(DataSet.dataset_key == key))
        if dataset is None:
            raise ApplicationError("dataset_not_found", "Dataset not found.", 404)
        return dataset

    async def register(self, entry: dict, actor: User | None) -> DataSet:
        """Create or refresh a dataset from a manifest entry.

        Descriptive metadata always follows the manifest. Decisions an administrator has recorded in the database
        (publication state, enabled flag, an owner rights confirmation and the licence status it granted) are never
        overwritten by a later sync.
        """
        dataset = await self.session.scalar(select(DataSet).where(DataSet.dataset_key == entry["id"]))
        fields = dict(
            name=entry["name"], purpose=entry["purpose"], entity_type=entry.get("entity_type", "unspecified"),
            source_name=entry["source"]["name"], source_url=entry["source"].get("url"), version=entry["source"].get("version"),
            date_acquired=_date(entry.get("date_acquired")), license_name=entry["license"].get("name"),
            provenance=entry["provenance"], transformation=entry.get("transformation"),
            importer=entry.get("importer"), importer_version=entry.get("importer_version"), checksum_sha256=entry.get("checksum_sha256"),
            validation_status=entry["validation_status"], readiness=entry["readiness"], remaining_action=entry.get("remaining_action"),
            last_checked=_date(entry.get("last_checked")))
        if dataset is None:
            allowed, _ = can_publish(license_status=entry["license"]["status"], validation_status=entry["validation_status"], rights_confirmation=entry.get("rights_confirmation"))
            dataset = DataSet(dataset_key=entry["id"], license_status=entry["license"]["status"], rights_confirmation=entry.get("rights_confirmation"),
                              publication_status="published" if entry["publication_status"] == "published" and allowed else "staged", **fields)
            self.session.add(dataset)
            await self.session.flush()
            await self.audit(actor, "dataset.registered", "data_set", dataset.id, {"key": entry["id"], "publication_status": dataset.publication_status})
        else:
            for name, value in fields.items():
                setattr(dataset, name, value)
            if dataset.license_status != "OWNER_PERMISSION_GRANTED":
                dataset.license_status = entry["license"]["status"]
            if not dataset.rights_confirmation:
                dataset.rights_confirmation = entry.get("rights_confirmation")
        return dataset

    async def apply_action(self, key: str, action: str, actor: User, *, note: str | None = None, rights_confirmation: dict | None = None) -> DataSet:
        if action not in ACTIONS:
            raise ApplicationError("invalid_action", f"Action must be one of {', '.join(sorted(ACTIONS))}.", 422)
        dataset = await self.by_key(key)
        before = dataset.publication_status
        if action == "publish":
            if rights_confirmation:
                dataset.rights_confirmation = {**rights_confirmation, "recorded_by": str(actor.id)}
                if dataset.license_status in {"LICENSE_REQUIRED", "UNKNOWN", "PROVENANCE_UNCLEAR"}:
                    dataset.license_status = "OWNER_PERMISSION_GRANTED"
            allowed, reasons = can_publish(license_status=dataset.license_status, validation_status=dataset.validation_status,
                                           rights_confirmation=dataset.rights_confirmation)
            if not allowed:
                raise ApplicationError("publication_not_permitted", "This dataset cannot be published yet.", 409, {"reasons": list(reasons)})
            dataset.publication_status, dataset.enabled = "published", True
        elif action == "mark_verified":
            if not note or len(note.strip()) < 10:
                raise ApplicationError("note_required", "Explain what was checked (at least 10 characters).", 422)
            dataset.validation_status = "VERIFIED"
        elif action in {"stage", "unpublish"}:  # unpublish withdraws a published dataset from every reader without deleting it
            dataset.publication_status = "staged"
        elif action == "disable":
            dataset.enabled = False
        elif action == "enable":
            dataset.enabled = True
        elif action == "reject":
            dataset.publication_status, dataset.enabled = "rejected", False
        await self.audit(actor, f"dataset.{action}", "data_set", dataset.id, {"key": key, "from": before, "to": dataset.publication_status, "note": note})
        return dataset

    # -------------------------------------------------------------- knowledge records
    async def _failed_import(self, dataset: DataSet, file_sha: str, failures: list[dict], importer_version: str, actor: User | None, total: int, source: dict | None = None) -> DataSetImport:
        """A strict import with any invalid row changes nothing; the attempt and its errors are still recorded for review."""
        imp = DataSetImport(dataset_id=dataset.id, file_sha256=file_sha, importer_version=importer_version, status="failed",
                            failed_count=len(failures), failures=failures[:MAX_ERRORS_REPORTED], imported_by_user_id=actor.id if actor else None, **_source_fields(source))
        self.session.add(imp)
        await self.session.flush()
        await self.audit(actor, "dataset.import_failed", "data_set_import", imp.id, {"key": dataset.dataset_key, "rows": total, "failed": len(failures)})
        return imp

    async def preview_records(self, key: str, rows: Sequence[object]) -> dict:
        """Validate and diff a file against the database without writing anything."""
        dataset = await self.by_key(key)
        batch = validate_record_batch(rows, expected_type=dataset.entity_type if dataset.entity_type != "unspecified" else None)
        existing = {r.record_key: r.content_sha256 for r in (await self.session.execute(select(KnowledgeRecord.record_key, KnowledgeRecord.content_sha256).where(KnowledgeRecord.dataset_id == dataset.id)))}
        create = update = same = 0
        for record in batch.valid:
            if record.id not in existing:
                create += 1
            elif existing[record.id] == record.content_hash():
                same += 1
            else:
                update += 1
        return {"rows": len(rows), "valid": len(batch.valid), "would_create": create, "would_update": update, "unchanged": same,
                "failed": len(batch.failures), "failures": batch.failures[:MAX_ERRORS_REPORTED]}

    async def preview_listings(self, key: str, rows: Sequence[object]) -> dict:
        dataset = await self.by_key(key)
        valid, failures = _validate_listings(rows)
        existing = {l.external_key for l in (await self.session.scalars(select(DirectoryListing).where(DirectoryListing.dataset_id == dataset.id, DirectoryListing.external_key.is_not(None)))).all()}
        create = sum(1 for item in valid if item.external_key not in existing)
        return {"rows": len(rows), "valid": len(valid), "would_create": create, "would_update_or_unchanged": len(valid) - create,
                "failed": len(failures), "failures": failures[:MAX_ERRORS_REPORTED]}

    async def import_records(self, key: str, rows: Sequence[object], actor: User | None, *, importer_version: str = IMPORTER_VERSION, strict: bool = True,
        max_records: int = MAX_RECORDS_PER_UPLOAD, source: dict | None = None) -> DataSetImport:
        dataset = await self.by_key(key)
        if len(rows) > max_records:
            raise ApplicationError("too_many_records", f"At most {max_records} records per upload.", 413)
        file_sha = sha256_json(rows)
        previous = await self.session.scalar(select(DataSetImport).where(
            DataSetImport.dataset_id == dataset.id, DataSetImport.file_sha256 == file_sha, DataSetImport.status == "applied"))
        if previous is not None:
            return previous  # idempotent: the same file applied twice changes nothing
        batch = validate_record_batch(rows, expected_type=dataset.entity_type if dataset.entity_type != "unspecified" else None)
        if strict and batch.failures:
            return await self._failed_import(dataset, file_sha, batch.failures, importer_version, actor, len(rows), source)
        imp = DataSetImport(dataset_id=dataset.id, file_sha256=file_sha, importer_version=importer_version, imported_by_user_id=actor.id if actor else None, **_source_fields(source))
        self.session.add(imp)
        await self.session.flush()
        existing = {r.record_key: r for r in (await self.session.scalars(select(KnowledgeRecord).where(KnowledgeRecord.dataset_id == dataset.id))).all()}
        created = updated = unchanged = 0
        snapshot: list[dict] = []
        for record in batch.valid:
            digest = record.content_hash()
            current = existing.get(record.id)
            values = dict(
                entity_type=record.entity_type, title=record.title, arabic_title=record.arabic_title, description=record.description,
                source=record.source, source_url=record.source_url, author=record.author, record_date=record.date, license=record.license,
                provenance=record.provenance, scholarly_status=record.scholarly_status, confidence=record.confidence,
                last_verified=record.last_verified, tags=record.tags, relationships=[r.model_dump() for r in record.relationships],
                source_work=record.source_work, edition=record.edition, volume=record.volume, page=record.page, chapter=record.chapter,
                language=record.language, publication_status=record.publication_status, license_status=record.license_status,
                provenance_status=record.provenance_status, attributes=record.attributes, content_sha256=digest)
            if current is None:
                self.session.add(KnowledgeRecord(dataset_id=dataset.id, import_id=imp.id, record_key=record.id, **values))
                created += 1
            elif current.content_sha256 == digest:
                unchanged += 1
            else:
                snapshot.append({"record_key": current.record_key, "previous_import_id": str(current.import_id) if current.import_id else None,
                                 "values": _jsonable({k: getattr(current, k) for k in values})})
                for name, value in values.items():
                    setattr(current, name, value)
                current.import_id = imp.id
                updated += 1
        imp.created_count, imp.updated_count, imp.unchanged_count = created, updated, unchanged
        imp.failed_count, imp.failures, imp.snapshot = len(batch.failures), batch.failures[:MAX_ERRORS_REPORTED], snapshot
        if created or updated:
            dataset.validation_status = "NEEDS_REVIEW"  # an import is never self-verifying: a person marks it verified
        await self.session.flush()
        dataset.record_count = await self.session.scalar(select(func.count()).select_from(KnowledgeRecord).where(KnowledgeRecord.dataset_id == dataset.id)) or 0
        dataset.checksum_sha256 = file_sha
        dataset.importer_version = importer_version
        await self.audit(actor, "dataset.import", "data_set_import", imp.id, {"key": key, "created": created, "updated": updated, "failed": len(batch.failures)})
        return imp

    async def rollback_import(self, import_id: UUID, actor: User) -> DataSetImport:
        imp = await self.session.get(DataSetImport, import_id)
        if imp is None:
            raise ApplicationError("import_not_found", "Import not found.", 404)
        if imp.status != "applied":
            raise ApplicationError("import_not_active", "Only an applied import can be rolled back.", 409)
        restored = {item["record_key"]: item for item in imp.snapshot}
        for record_key, item in restored.items():
            record = await self.session.scalar(select(KnowledgeRecord).where(KnowledgeRecord.dataset_id == imp.dataset_id, KnowledgeRecord.record_key == record_key))
            if record is not None:
                for name, value in item["values"].items():
                    setattr(record, name, _revive(name, value))
                record.import_id = UUID(item["previous_import_id"]) if item["previous_import_id"] else None
        await self.session.execute(delete(KnowledgeRecord).where(KnowledgeRecord.import_id == imp.id))
        await self.session.execute(delete(DirectoryListing).where(DirectoryListing.import_id == imp.id))
        imp.status, imp.rolled_back_at = "rolled_back", datetime.now(UTC)
        await self.session.flush()
        dataset = await self.session.get(DataSet, imp.dataset_id)
        if dataset is not None:
            dataset.record_count = await self.session.scalar(select(func.count()).select_from(KnowledgeRecord).where(KnowledgeRecord.dataset_id == dataset.id)) or 0
        await self.audit(actor, "dataset.import_rolled_back", "data_set_import", imp.id, {"restored": len(restored)})
        return imp

    # -------------------------------------------------------------- directory listings
    async def import_listings(self, key: str, rows: Sequence[object], actor: User | None, *, importer_version: str = IMPORTER_VERSION, strict: bool = True,
        max_records: int = MAX_RECORDS_PER_UPLOAD, source: dict | None = None) -> DataSetImport:
        dataset = await self.by_key(key)
        if len(rows) > max_records:
            raise ApplicationError("too_many_records", f"At most {max_records} records per upload.", 413)
        file_sha = sha256_json(rows)
        previous = await self.session.scalar(select(DataSetImport).where(
            DataSetImport.dataset_id == dataset.id, DataSetImport.file_sha256 == file_sha, DataSetImport.status == "applied"))
        if previous is not None:
            return previous
        valid, failures = _validate_listings(rows)
        if strict and failures:
            return await self._failed_import(dataset, file_sha, failures, importer_version, actor, len(rows), source)
        imp = DataSetImport(dataset_id=dataset.id, file_sha256=file_sha, importer_version=importer_version, imported_by_user_id=actor.id if actor else None, **_source_fields(source))
        self.session.add(imp)
        await self.session.flush()
        created = updated = unchanged = 0
        existing = {l.external_key: l for l in (await self.session.scalars(select(DirectoryListing).where(
            DirectoryListing.dataset_id == dataset.id, DirectoryListing.external_key.is_not(None)))).all()}
        for item in valid:
            values = item.model_dump(exclude={"external_key"})
            current = existing.get(item.external_key) if item.external_key else None
            if current is None:
                self.session.add(DirectoryListing(dataset_id=dataset.id, import_id=imp.id, external_key=item.external_key, status="published",
                                                  dedupe_key=item.key, **values))
                created += 1
            else:
                changed = False
                for name, value in values.items():
                    if getattr(current, name) != value:
                        setattr(current, name, value)
                        changed = True
                if changed:
                    updated += 1  # import_id stays with the creating import, so a rollback never deletes updated rows
                else:
                    unchanged += 1
        imp.created_count, imp.updated_count, imp.unchanged_count = created, updated, unchanged
        imp.failed_count, imp.failures = len(failures), failures[:MAX_ERRORS_REPORTED]
        await self.session.flush()
        dataset.record_count = await self.session.scalar(select(func.count()).select_from(DirectoryListing).where(DirectoryListing.dataset_id == dataset.id)) or 0
        if created or updated:
            dataset.validation_status = "NEEDS_REVIEW"
        dataset.checksum_sha256, dataset.importer_version = file_sha, importer_version
        await self.audit(actor, "dataset.import_listings", "data_set_import", imp.id, {"key": key, "created": created, "updated": updated, "failed": len(failures)})
        return imp


def _validate_listings(rows: Sequence[object]) -> tuple[list[DirectoryListingInput], list[dict]]:
    """Validate every row independently; duplicates inside the file are reported, never silently merged."""
    valid: list[DirectoryListingInput] = []
    failures: list[dict] = []
    seen: set[str] = set()
    for position, row in enumerate(rows):
        try:
            item = DirectoryListingInput.model_validate(row)
        except Exception as exc:
            errors = [f"{'.'.join(str(p) for p in e.get('loc', ()))}: {e.get('msg')}" for e in getattr(exc, "errors", lambda: [])()] or [str(exc)]
            failures.append({"index": position, "id": row.get("external_key") if isinstance(row, dict) else None, "errors": errors})
            continue
        identity = item.external_key or item.key
        if identity in seen:
            failures.append({"index": position, "id": identity, "errors": ["duplicate listing in file"]})
            continue
        seen.add(identity)
        valid.append(item)
    return valid, failures


def _source_fields(source: dict | None) -> dict:
    """adapter_id, source_version, source_retrieved_at, source_checksum for the import row (empty for manual uploads)."""
    return {k: v for k, v in (source or {}).items() if k in {"adapter_id", "source_version", "source_retrieved_at", "source_checksum"}}


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _jsonable(values: dict) -> dict:
    return {k: (v.isoformat() if isinstance(v, date) else v) for k, v in values.items()}


def _revive(name: str, value):
    return date.fromisoformat(value) if name == "last_verified" and isinstance(value, str) else value
