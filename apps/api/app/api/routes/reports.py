from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import MembershipContext, require_permission
from app.db.session import get_db
from app.schemas.reporting import DashboardReportOut
from app.services.reporting_service import ReportingService

router = APIRouter(prefix="/tenants/me/reports", tags=["reports"])


@router.get("/dashboard", response_model=DashboardReportOut)
def get_dashboard_report(
    db: Session = Depends(get_db),
    ctx: MembershipContext = Depends(require_permission("reports.view")),
) -> DashboardReportOut:
    report = ReportingService(db).get_dashboard_report(ctx.tenant_id)
    return DashboardReportOut.model_validate(report)
