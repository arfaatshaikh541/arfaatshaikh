"""Automated data-quality report and conflict detection. Reports problems; never repairs them.

Questionable records are surfaced for a human (an administrator can hide a listing or link a duplicate); the data itself is
not renamed, merged or corrected here, because a "correction" without evidence would be an invention.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_contract import DataSet, DirectoryListing, KnowledgeRecord
from app.services.data_contracts import haversine_km, normalise_name
from app.services.manifest import manifest_path
from app.services.readiness import live_state

CELL_DEGREES = 0.001  # about 110 m in latitude; neighbouring cells are compared too
DUPLICATE_RADIUS_M = 50.0
SIMILAR_RADIUS_M = 100.0
SIMILAR_RATIO = 0.85
COLOCATED_RADIUS_M = 25.0
CAP = 200
# A mosque record whose own name says it is another kind of building: reported, never corrected.
NON_MOSQUE_WORDS = re.compile(r"\b(synagogue|synagogu|church|cathedral|eglise|église|basilique|chapel|chapelle|temple|kirche|iglesia)\b", re.I)


def source_quality_notes_path() -> Path:
    return manifest_path().parent / "source-quality-notes.json"


def load_source_quality_notes() -> list[dict]:
    path = source_quality_notes_path()
    return json.loads(path.read_text(encoding="utf-8"))["notes"] if path.exists() else []


def _valid_url(value: str | None) -> bool:
    if not value:
        return True
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname)


def find_listing_conflicts(items: Iterable[dict]) -> dict[str, list[dict]]:
    """items: {id, key, name, arabic_name, lat, lon, duplicate_of, denomination, type}.

    duplicate_candidates      same normalised name within 50 m and not yet linked as a duplicate
    similar_names             near-identical (not equal) normalised names within 100 m: suspicious, not certain
    co_located_different      two named listings within 25 m whose names differ (the source disagrees with itself or maps two places)
    denomination_conflicts    near-identical names within 50 m that state different denominations
    non_mosque_names          a mosque record whose name mentions another kind of building
    Deterministic: ordering depends only on ids.
    """
    rows = sorted((i for i in items if i["lat"] is not None and i["lon"] is not None), key=lambda i: str(i["id"]))
    grid: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for row in rows:
        grid[(round(row["lat"] / CELL_DEGREES), round(row["lon"] / CELL_DEGREES))].append(row)
    out: dict[str, list[dict]] = {"duplicate_candidates": [], "similar_names": [], "co_located_different": [], "denomination_conflicts": [], "non_mosque_names": []}
    seen: set[tuple[str, str]] = set()
    for (cx, cy), cell in grid.items():
        near = [r for dx in (-1, 0, 1) for dy in (-1, 0, 1) for r in grid.get((cx + dx, cy + dy), [])]
        for a in cell:
            for b in near:
                if str(a["id"]) >= str(b["id"]):
                    continue
                pair = (str(a["id"]), str(b["id"]))
                if pair in seen:
                    continue
                meters = haversine_km(a["lat"], a["lon"], b["lat"], b["lon"]) * 1000
                if meters > SIMILAR_RADIUS_M:
                    continue
                seen.add(pair)
                na, nb = normalise_name(a["name"]), normalise_name(b["name"])
                aa, ab = normalise_name(a.get("arabic_name") or ""), normalise_name(b.get("arabic_name") or "")
                same = bool(na) and na == nb or bool(aa) and aa == ab
                detail = {"a": a["id"], "b": b["id"], "a_name": a["name"], "b_name": b["name"], "a_key": a.get("key"), "b_key": b.get("key"), "distance_m": round(meters, 1)}
                if same and meters <= DUPLICATE_RADIUS_M:
                    if not a.get("duplicate_of") and not b.get("duplicate_of"):
                        out["duplicate_candidates"].append(detail)
                    if a.get("denomination") and b.get("denomination") and a["denomination"] != b["denomination"]:
                        out["denomination_conflicts"].append({**detail, "a_denomination": a["denomination"], "b_denomination": b["denomination"]})
                elif na and nb and not same and SequenceMatcher(None, na, nb).ratio() >= SIMILAR_RATIO:
                    out["similar_names"].append(detail)
                elif na and nb and not same and meters <= COLOCATED_RADIUS_M and SequenceMatcher(None, na, nb).ratio() < 0.5:
                    out["co_located_different"].append(detail)
    for row in rows:
        if row.get("type") == "mosque" and NON_MOSQUE_WORDS.search(f"{row['name']} {row.get('arabic_name') or ''}"):
            out["non_mosque_names"].append({"id": row["id"], "key": row.get("key"), "name": row["name"], "arabic_name": row.get("arabic_name")})
    for kind in out:
        out[kind].sort(key=lambda d: (str(d.get("a", d.get("id"))), str(d.get("b", ""))))
    return out


async def listing_items(db: AsyncSession, dataset_key: str | None = None) -> list[dict]:
    stmt = select(DirectoryListing)
    if dataset_key:
        stmt = stmt.where(DirectoryListing.dataset_id == select(DataSet.id).where(DataSet.dataset_key == dataset_key).scalar_subquery())
    return [{"id": str(r.id), "key": r.external_key, "name": r.name, "arabic_name": r.arabic_name, "lat": r.latitude, "lon": r.longitude, "duplicate_of": r.duplicate_of_id,
             "denomination": (r.attributes or {}).get("denomination"), "type": r.listing_type} for r in (await db.scalars(stmt)).all()]


async def dataset_conflicts(db: AsyncSession, dataset_key: str, limit: int = CAP) -> dict:
    dataset = (await db.scalars(select(DataSet).where(DataSet.dataset_key == dataset_key))).one()
    if dataset.entity_type in {"mosque", "business", "charity", "job", "professional", "organisation", "event", "volunteering", "health"}:
        found = find_listing_conflicts(await listing_items(db, dataset_key))
        return {"dataset": dataset_key, "kind": "listings", "totals": {k: len(v) for k, v in found.items()}, "items": {k: v[:limit] for k, v in found.items()},
                "note": "Reported for review. Nothing is merged, renamed or corrected automatically."}
    rows = (await db.scalars(select(KnowledgeRecord).where(KnowledgeRecord.dataset_id == dataset.id))).all()
    differing = [{"id": r.record_key, "title": r.title, "grades": [{"grader": g["grader"], "grade": g["grade"]} for g in (r.attributes or {}).get("grades", [])]}
                 for r in rows if (r.attributes or {}).get("grade_labels_differ")]
    titles: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for r in rows:
        titles[(r.entity_type, normalise_name(r.title), r.author or "")].append(r.record_key)
    dupes = [{"title": k[1], "ids": v} for k, v in titles.items() if len(v) > 1]
    return {"dataset": dataset_key, "kind": "records", "totals": {"grader_labels_differ": len(differing), "duplicate_titles": len(dupes)},
            "items": {"grader_labels_differ": differing[:limit], "duplicate_titles": dupes[:limit]},
            "note": "Differing grades from different graders are source disagreement, not an error; they are shown side by side and never reconciled."}


async def quality_report(db: AsyncSession) -> dict:
    now = datetime.now(UTC)
    live = await live_state(db)
    kr_total = await db.scalar(select(func.count()).select_from(KnowledgeRecord)) or 0
    published_ids = select(DataSet.id).where(DataSet.publication_status == "published", DataSet.enabled.is_(True))
    kr_published = await db.scalar(select(func.count()).select_from(KnowledgeRecord).where(KnowledgeRecord.dataset_id.in_(published_ids))) or 0
    kr = {
        "total": kr_total, "published": kr_published, "hidden": kr_total - kr_published,
        "unverified": await db.scalar(select(func.count()).select_from(KnowledgeRecord).where(KnowledgeRecord.scholarly_status == "unreviewed")) or 0,
        "missing_names": await db.scalar(select(func.count()).select_from(KnowledgeRecord).where(func.length(func.trim(KnowledgeRecord.title)) < 1)) or 0,
        "missing_source_ids": await db.scalar(select(func.count()).select_from(KnowledgeRecord).where(func.length(func.trim(KnowledgeRecord.record_key)) < 1)) or 0,
        "missing_provenance": await db.scalar(select(func.count()).select_from(KnowledgeRecord).where(func.length(func.trim(KnowledgeRecord.provenance)) < 3)) or 0,
        "provenance_status_unclear": await db.scalar(select(func.count()).select_from(KnowledgeRecord).where(KnowledgeRecord.provenance_status == "unclear")) or 0,
        "without_licence_metadata": await db.scalar(select(func.count()).select_from(KnowledgeRecord).where(or_(func.length(func.trim(KnowledgeRecord.license)) < 1, KnowledgeRecord.license_status == "UNKNOWN"))) or 0,
        "without_verification_status": await db.scalar(select(func.count()).select_from(KnowledgeRecord).where(KnowledgeRecord.scholarly_status.is_(None))) or 0,
        "invalid_urls": 0, "orphaned_relationships": 0, "grader_labels_differ": 0,
    }
    keys = {r for (r,) in (await db.execute(select(KnowledgeRecord.record_key))).all()}
    for source_url, relationships, attributes in (await db.execute(select(KnowledgeRecord.source_url, KnowledgeRecord.relationships, KnowledgeRecord.attributes))).all():
        kr["invalid_urls"] += 0 if _valid_url(source_url) and _valid_url((attributes or {}).get("external_url")) else 1
        kr["orphaned_relationships"] += sum(1 for rel in relationships or [] if rel.get("target_id") not in keys)
        kr["grader_labels_differ"] += 1 if (attributes or {}).get("grade_labels_differ") else 0
    listings = (await db.scalars(select(DirectoryListing))).all()
    visible_ids = {i for (i,) in (await db.execute(select(DirectoryListing.id).where(DirectoryListing.status == "published", DirectoryListing.duplicate_of_id.is_(None)))).all()}
    dl = {"total": len(listings), "published_visible": 0, "hidden": 0, "unverified": 0, "missing_names": 0, "missing_source_ids": 0, "missing_provenance": 0, "duplicates_linked": 0,
          "invalid_urls": 0, "expired": 0, "without_licence_metadata": 0, "without_verification_status": 0}
    for r in listings:
        event_end = r.ends_at or (r.starts_at + timedelta(hours=6) if r.starts_at else None)  # the same rule as the public filter
        expired = bool((r.expires_at and r.expires_at <= now) or (r.listing_type == "event" and event_end is not None and event_end <= now))
        dl["expired"] += expired
        dl["published_visible"] += r.id in visible_ids and not expired
        dl["unverified"] += r.verification_status != "verified"
        dl["missing_names"] += len((r.name or "").strip()) < 2
        a = r.attributes or {}
        dl["missing_source_ids"] += bool(r.dataset_id) and not (r.external_key or a.get("osm") or a.get("wikidata"))
        dl["missing_provenance"] += len((r.provenance or "").strip()) < 3
        dl["duplicates_linked"] += r.duplicate_of_id is not None
        dl["invalid_urls"] += not (_valid_url(r.website) and _valid_url(r.source_url) and _valid_url(a.get("application_url")) and _valid_url(a.get("registration_url")))
        dl["without_licence_metadata"] += not (r.license or "").strip()
        dl["without_verification_status"] += not (r.verification_status or "").strip()
    dl["hidden"] = dl["total"] - dl["published_visible"]
    conflicts = find_listing_conflicts([{"id": str(r.id), "key": r.external_key, "name": r.name, "arabic_name": r.arabic_name, "lat": r.latitude, "lon": r.longitude,
                                         "duplicate_of": r.duplicate_of_id, "denomination": (r.attributes or {}).get("denomination"), "type": r.listing_type} for r in listings])
    by_country: dict[str, int] = defaultdict(int)
    for r in listings:
        if r.id in visible_ids:
            by_country[(r.country or "??") + ":" + r.listing_type] += 1
    notes = load_source_quality_notes()
    present = {r.external_key for r in listings}
    return {"generated_at": now.isoformat(), "domains": {k: v for k, v in sorted(live["counts"].items())}, "knowledge_records": kr, "directory_listings": dl,
            "conflicts": {"totals": {k: len(v) for k, v in conflicts.items()}, "examples": {k: v[:20] for k, v in conflicts.items()}},
            "coverage": dict(sorted(by_country.items())),
            "source_quality_notes": [{**n, "record_present": n["record_key"] in present} for n in notes]}
