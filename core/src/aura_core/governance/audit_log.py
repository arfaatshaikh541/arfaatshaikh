"""Audit Log: hash-chained, append-only, tamper-evident.

Every entry's hash covers the previous entry's hash plus its own fields, so
altering or deleting any past entry breaks the chain from that point
forward — detectable by verify_chain(). This is the store the Security
Guardian (future work) holds an independent read path to; nothing here
lets a caller edit or delete a past entry, only append new ones.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from ..memory.models import Base
from .models import AuditEntry

GENESIS_HASH = "0" * 64


def _digest(
    *, prev_hash: str, timestamp_iso: str, actor: str, action_type: str, params_json: str,
    risk_tier: str, decision: str, approval_id: str | None, result_status: str, result_message: str,
) -> str:
    canonical = json.dumps(
        {
            "prev_hash": prev_hash,
            "timestamp_iso": timestamp_iso,
            "actor": actor,
            "action_type": action_type,
            "params_json": params_json,
            "risk_tier": risk_tier,
            "decision": decision,
            "approval_id": approval_id,
            "result_status": result_status,
            "result_message": result_message,
        },
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class ChainVerification:
    valid: bool
    broken_at_seq: int | None
    entries_checked: int


class AuditLog:
    def __init__(self, database_url: str) -> None:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self._engine = create_engine(database_url, connect_args=connect_args)
        Base.metadata.create_all(self._engine)
        self._Session = sessionmaker(bind=self._engine)

    def record(
        self, *, actor: str, action_type: str, params_json: str, risk_tier: str,
        decision: str, approval_id: str | None, result_status: str, result_message: str,
    ) -> AuditEntry:
        with self._Session() as session:
            last = session.scalars(select(AuditEntry).order_by(AuditEntry.seq.desc())).first()
            prev_hash = last.hash if last else GENESIS_HASH
            timestamp_iso = datetime.now(timezone.utc).isoformat()

            digest = _digest(
                prev_hash=prev_hash, timestamp_iso=timestamp_iso, actor=actor,
                action_type=action_type, params_json=params_json, risk_tier=risk_tier,
                decision=decision, approval_id=approval_id, result_status=result_status,
                result_message=result_message,
            )

            entry = AuditEntry(
                timestamp_iso=timestamp_iso, actor=actor, action_type=action_type,
                params_json=params_json, risk_tier=risk_tier, decision=decision,
                approval_id=approval_id, result_status=result_status, result_message=result_message,
                prev_hash=prev_hash, hash=digest,
            )
            session.add(entry)
            session.commit()
            session.refresh(entry)
            return entry

    def all_entries(self) -> list[AuditEntry]:
        with self._Session() as session:
            return list(session.scalars(select(AuditEntry).order_by(AuditEntry.seq)))

    def verify_chain(self) -> ChainVerification:
        entries = self.all_entries()
        prev_hash = GENESIS_HASH
        for entry in entries:
            expected = _digest(
                prev_hash=prev_hash, timestamp_iso=entry.timestamp_iso, actor=entry.actor,
                action_type=entry.action_type, params_json=entry.params_json,
                risk_tier=entry.risk_tier, decision=entry.decision, approval_id=entry.approval_id,
                result_status=entry.result_status, result_message=entry.result_message,
            )
            if entry.prev_hash != prev_hash or entry.hash != expected:
                return ChainVerification(valid=False, broken_at_seq=entry.seq, entries_checked=len(entries))
            prev_hash = entry.hash
        return ChainVerification(valid=True, broken_at_seq=None, entries_checked=len(entries))
