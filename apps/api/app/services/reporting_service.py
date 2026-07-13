"""Module 13: dashboard reporting.

Every figure here is a live SQL aggregate, tenant-scoped the same way
every other query in the codebase is - there is no separate reporting
data store, cache, or nightly rollup for v1. That's a deliberate,
documented tradeoff (see docs/architecture/erd-summary-m5.md), not an
oversight: it keeps the numbers always current at the cost of doing the
aggregation on every request, which is fine at demo/small-tenant scale.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models.appointment import Appointment
from app.models.lead import Lead
from app.models.membership import Membership
from app.models.pipeline import PipelineStage
from app.models.task import Task
from app.models.user import User


@dataclass
class OverviewStats:
    total_leads: int
    hot_leads: int
    open_tasks: int
    overdue_tasks: int
    upcoming_appointments: int


@dataclass
class FunnelStage:
    stage_id: uuid.UUID
    name: str
    sort_order: int
    is_won: bool
    is_lost: bool
    lead_count: int


@dataclass
class SourceCount:
    source: str
    count: int


@dataclass
class PriorityCount:
    priority: str
    count: int


@dataclass
class MemberPerformance:
    membership_id: uuid.UUID
    member_name: str
    leads_assigned: int
    leads_won: int


@dataclass
class TaskStats:
    open: int
    overdue: int
    completed_last_30_days: int


@dataclass
class AppointmentStats:
    scheduled: int
    confirmed: int
    completed: int
    cancelled: int
    no_show: int


@dataclass
class DashboardReport:
    overview: OverviewStats
    pipeline_funnel: list[FunnelStage] = field(default_factory=list)
    lead_sources: list[SourceCount] = field(default_factory=list)
    score_distribution: list[PriorityCount] = field(default_factory=list)
    team_performance: list[MemberPerformance] = field(default_factory=list)
    task_stats: TaskStats = field(default_factory=lambda: TaskStats(0, 0, 0))
    appointment_stats: AppointmentStats = field(
        default_factory=lambda: AppointmentStats(0, 0, 0, 0, 0)
    )


class ReportingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_dashboard_report(self, tenant_id: uuid.UUID) -> DashboardReport:
        return DashboardReport(
            overview=self._overview(tenant_id),
            pipeline_funnel=self._pipeline_funnel(tenant_id),
            lead_sources=self._lead_sources(tenant_id),
            score_distribution=self._score_distribution(tenant_id),
            team_performance=self._team_performance(tenant_id),
            task_stats=self._task_stats(tenant_id),
            appointment_stats=self._appointment_stats(tenant_id),
        )

    def _overview(self, tenant_id: uuid.UUID) -> OverviewStats:
        now = utcnow()
        total_leads = self.db.execute(
            select(func.count()).select_from(Lead).where(Lead.tenant_id == tenant_id)
        ).scalar_one()
        hot_leads = self.db.execute(
            select(func.count())
            .select_from(Lead)
            .where(Lead.tenant_id == tenant_id, Lead.priority == "hot")
        ).scalar_one()
        open_tasks = self.db.execute(
            select(func.count())
            .select_from(Task)
            .where(Task.tenant_id == tenant_id, Task.status == "open")
        ).scalar_one()
        overdue_tasks = self.db.execute(
            select(func.count())
            .select_from(Task)
            .where(
                Task.tenant_id == tenant_id,
                Task.status == "open",
                Task.due_at.is_not(None),
                Task.due_at < now,
            )
        ).scalar_one()
        upcoming_appointments = self.db.execute(
            select(func.count())
            .select_from(Appointment)
            .where(
                Appointment.tenant_id == tenant_id,
                Appointment.status.in_(("scheduled", "confirmed")),
                Appointment.starts_at >= now,
                Appointment.starts_at < now + timedelta(days=7),
            )
        ).scalar_one()
        return OverviewStats(
            total_leads=int(total_leads),
            hot_leads=int(hot_leads),
            open_tasks=int(open_tasks),
            overdue_tasks=int(overdue_tasks),
            upcoming_appointments=int(upcoming_appointments),
        )

    def _pipeline_funnel(self, tenant_id: uuid.UUID) -> list[FunnelStage]:
        stmt = (
            select(PipelineStage, func.count(Lead.id))
            .outerjoin(Lead, and_(Lead.stage_id == PipelineStage.id, Lead.tenant_id == tenant_id))
            .where(PipelineStage.tenant_id == tenant_id)
            .group_by(PipelineStage.id)
            .order_by(PipelineStage.sort_order)
        )
        return [
            FunnelStage(
                stage_id=stage.id,
                name=stage.name,
                sort_order=stage.sort_order,
                is_won=stage.is_won,
                is_lost=stage.is_lost,
                lead_count=int(count),
            )
            for stage, count in self.db.execute(stmt).all()
        ]

    def _lead_sources(self, tenant_id: uuid.UUID) -> list[SourceCount]:
        stmt = (
            select(Lead.source, func.count(Lead.id))
            .where(Lead.tenant_id == tenant_id)
            .group_by(Lead.source)
            .order_by(func.count(Lead.id).desc())
        )
        return [
            SourceCount(source=source, count=int(count))
            for source, count in self.db.execute(stmt).all()
        ]

    def _score_distribution(self, tenant_id: uuid.UUID) -> list[PriorityCount]:
        stmt = (
            select(Lead.priority, func.count(Lead.id))
            .where(Lead.tenant_id == tenant_id)
            .group_by(Lead.priority)
        )
        return [
            PriorityCount(priority=priority, count=int(count))
            for priority, count in self.db.execute(stmt).all()
        ]

    def _team_performance(self, tenant_id: uuid.UUID) -> list[MemberPerformance]:
        assigned_stmt = (
            select(Membership.id, User.first_name, User.last_name, func.count(Lead.id))
            .select_from(Membership)
            .join(User, User.id == Membership.user_id)
            .outerjoin(
                Lead,
                and_(Lead.assigned_membership_id == Membership.id, Lead.tenant_id == tenant_id),
            )
            .where(Membership.tenant_id == tenant_id, Membership.status == "active")
            .group_by(Membership.id, User.first_name, User.last_name)
        )
        assigned_rows = {
            row[0]: (row[1], row[2], row[3]) for row in self.db.execute(assigned_stmt).all()
        }

        won_stmt = (
            select(Lead.assigned_membership_id, func.count(Lead.id))
            .select_from(Lead)
            .join(PipelineStage, PipelineStage.id == Lead.stage_id)
            .where(
                Lead.tenant_id == tenant_id,
                PipelineStage.is_won.is_(True),
                Lead.assigned_membership_id.is_not(None),
            )
            .group_by(Lead.assigned_membership_id)
        )
        won_counts = {
            membership_id: int(count) for membership_id, count in self.db.execute(won_stmt).all()
        }

        return [
            MemberPerformance(
                membership_id=membership_id,
                member_name=f"{first_name} {last_name}".strip(),
                leads_assigned=int(assigned_count),
                leads_won=won_counts.get(membership_id, 0),
            )
            for membership_id, (first_name, last_name, assigned_count) in assigned_rows.items()
        ]

    def _task_stats(self, tenant_id: uuid.UUID) -> TaskStats:
        now = utcnow()
        open_count = self.db.execute(
            select(func.count())
            .select_from(Task)
            .where(Task.tenant_id == tenant_id, Task.status == "open")
        ).scalar_one()
        overdue_count = self.db.execute(
            select(func.count())
            .select_from(Task)
            .where(
                Task.tenant_id == tenant_id,
                Task.status == "open",
                Task.due_at.is_not(None),
                Task.due_at < now,
            )
        ).scalar_one()
        completed_count = self.db.execute(
            select(func.count())
            .select_from(Task)
            .where(
                Task.tenant_id == tenant_id,
                Task.status == "completed",
                Task.completed_at.is_not(None),
                Task.completed_at >= now - timedelta(days=30),
            )
        ).scalar_one()
        return TaskStats(
            open=int(open_count),
            overdue=int(overdue_count),
            completed_last_30_days=int(completed_count),
        )

    def _appointment_stats(self, tenant_id: uuid.UUID) -> AppointmentStats:
        stmt = (
            select(Appointment.status, func.count(Appointment.id))
            .where(Appointment.tenant_id == tenant_id)
            .group_by(Appointment.status)
        )
        counts = {status: int(count) for status, count in self.db.execute(stmt).all()}
        return AppointmentStats(
            scheduled=counts.get("scheduled", 0),
            confirmed=counts.get("confirmed", 0),
            completed=counts.get("completed", 0),
            cancelled=counts.get("cancelled", 0),
            no_show=counts.get("no_show", 0),
        )
