import uuid

from app.schemas.common import ORMModel


class OverviewStatsOut(ORMModel):
    total_leads: int
    hot_leads: int
    open_tasks: int
    overdue_tasks: int
    upcoming_appointments: int


class FunnelStageOut(ORMModel):
    stage_id: uuid.UUID
    name: str
    sort_order: int
    is_won: bool
    is_lost: bool
    lead_count: int


class SourceCountOut(ORMModel):
    source: str
    count: int


class PriorityCountOut(ORMModel):
    priority: str
    count: int


class MemberPerformanceOut(ORMModel):
    membership_id: uuid.UUID
    member_name: str
    leads_assigned: int
    leads_won: int


class TaskStatsOut(ORMModel):
    open: int
    overdue: int
    completed_last_30_days: int


class AppointmentStatsOut(ORMModel):
    scheduled: int
    confirmed: int
    completed: int
    cancelled: int
    no_show: int


class DashboardReportOut(ORMModel):
    overview: OverviewStatsOut
    pipeline_funnel: list[FunnelStageOut]
    lead_sources: list[SourceCountOut]
    score_distribution: list[PriorityCountOut]
    team_performance: list[MemberPerformanceOut]
    task_stats: TaskStatsOut
    appointment_stats: AppointmentStatsOut
