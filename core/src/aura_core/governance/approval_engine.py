"""Approval Engine: the owner-facing pending-action queue.

Persisted (not in-memory), so a pending approval survives a process
restart — a real durability property, even without a full workflow engine
(Temporal) yet, per docs/roadmap.md's staged plan.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from ..memory.models import Base
from .models import ApprovalRecord
from .risk_engine import ActionRequest, RiskTier


class ApprovalEngine:
    def __init__(self, database_url: str) -> None:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self._engine = create_engine(database_url, connect_args=connect_args)
        Base.metadata.create_all(self._engine)
        self._Session = sessionmaker(bind=self._engine)

    def create(self, request: ActionRequest, risk_tier: RiskTier, reason: str) -> ApprovalRecord:
        with self._Session() as session:
            record = ApprovalRecord(
                action_type=request.action_type,
                params_json=json.dumps({
                    "params": request.params,
                    "amount": request.amount,
                    "budget_key": request.budget_key,
                }),
                requested_by=request.requested_by,
                risk_tier=risk_tier.value,
                reason=reason,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def get(self, approval_id: str) -> ApprovalRecord | None:
        with self._Session() as session:
            return session.get(ApprovalRecord, approval_id)

    def pending(self) -> list[ApprovalRecord]:
        with self._Session() as session:
            stmt = (
                select(ApprovalRecord)
                .where(ApprovalRecord.status == "pending")
                .order_by(ApprovalRecord.created_at)
            )
            return list(session.scalars(stmt))

    def decide(self, approval_id: str, *, approved: bool, decided_by: str) -> ApprovalRecord | None:
        with self._Session() as session:
            record = session.get(ApprovalRecord, approval_id)
            if record is None:
                return None
            record.status = "approved" if approved else "denied"
            record.decided_at = datetime.now(timezone.utc)
            record.decided_by = decided_by
            session.commit()
            session.refresh(record)
            return record

    @staticmethod
    def to_action_request(record: ApprovalRecord) -> ActionRequest:
        payload = json.loads(record.params_json)
        return ActionRequest(
            action_type=record.action_type,
            params=payload["params"],
            requested_by=record.requested_by,
            amount=payload.get("amount"),
            budget_key=payload.get("budget_key"),
        )
