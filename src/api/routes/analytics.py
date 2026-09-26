"""Dashboards (SRS Steps 61-63), analytics and trends (64-65), reports and exports (67-68).

Customers use the complaint list for their dashboard (`GET /complaints`); agents get their
department's work queue; reviewers, managers and administrators get the organisation-wide
dashboard, analytics and reports.
"""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from database.models import AnalysisRun, Complaint, Role, User
from database.session import get_db
from security.dependencies import STAFF_ROLES, require_roles
from src.analytics import metrics
from src.analytics.export import EXPORTERS, cell
from src.analytics.filters import Filters
from src.analytics.reports import REPORTS, Report, build_report
from src.analytics.trends import detect_trends
from src.api.schemas import (
    AdminDashboardOut,
    AgentDashboardOut,
    AgentQueueItem,
    AnalyticsOut,
    ReportOut,
    ReportSpecOut,
)
from src.core.domain import analysis_config, analytics_config

router = APIRouter(tags=["analytics"])
staff = require_roles(*STAFF_ROLES)
insight_roles = require_roles(Role.REVIEWER, Role.MANAGER, Role.ADMIN)

ADMIN_DIMENSIONS = (
    "category",
    "department",
    "priority",
    "status",
    "escalation_level",
    "sla_status",
    "verification",
)
ANALYTICS_DIMENSIONS = (
    "category",
    "subcategory",
    "product",
    "department",
    "urgency",
    "sentiment",
    "priority",
    "escalation_level",
    "channel",
    "customer_type",
)
PREVIEW_ROWS = 100
WARNING_SIGNALS = {
    "safety_hazard": "Safety hazard reported",
    "injury": "Injury reported",
    "legal_threat": "Legal action threatened",
    "privacy_exposure": "Personal data exposed",
    "account_compromise": "Possible account compromise",
    "prompt_injection": "Complaint contains instructions to the system",
}


def analytics_filters(
    date_from: date | None = Query(None, description="Submitted on or after (UTC)"),
    date_to: date | None = Query(None, description="Submitted on or before (UTC)"),
    category: str | None = None,
    department: str | None = None,
    priority: str | None = None,
    sentiment: str | None = None,
    channel: str | None = None,
    source: str | None = Query(None, description="portal, dataset or evaluation"),
) -> Filters:
    return Filters(date_from, date_to, category, department, priority, sentiment, channel, source)


@router.get("/dashboard/admin", response_model=AdminDashboardOut)
async def admin_dashboard(
    f: Filters = Depends(analytics_filters),
    _: User = Depends(insight_roles),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    limit = analytics_config()["dashboard"]["list_limit"]

    def build(s: Session) -> dict[str, Any]:
        reviews = metrics.manual_reviews(s, f)
        agreement = metrics.genai_python(s, f)
        return {
            "overview": metrics.overview(s, f),
            "distributions": {d: metrics.distribution(s, f, d) for d in ADMIN_DIMENSIONS},
            "departments": metrics.department_performance(s, f),
            "sla_risks": metrics.sla_risks(s, f, limit),
            "trends": [t.to_dict() for t in detect_trends(s, f)[:limit]],
            "agreement": {k: v for k, v in agreement.items() if k not in ("rows", "mismatches")},
            "reviews": {
                "open": reviews.open,
                "resolved": reviews.resolved,
                "avg_hours_to_resolve": reviews.avg_hours_to_resolve,
                "decisions": reviews.decisions,
                "top_reasons": reviews.top_reasons,
            },
        }

    return await db.run_sync(build)


@router.get("/analytics", response_model=AnalyticsOut)
async def analytics(
    f: Filters = Depends(analytics_filters),
    bucket: str = Query("day", pattern="^(day|week|month)$"),
    _: User = Depends(insight_roles),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    def build(s: Session) -> dict[str, Any]:
        return {
            "overview": metrics.overview(s, f),
            "volume": metrics.volume(s, f, bucket),
            "distributions": {d: metrics.distribution(s, f, d) for d in ANALYTICS_DIMENSIONS},
            "resolution_time": metrics.resolution_time(s, f),
            "departments": metrics.department_performance(s, f),
            "trends": [t.to_dict() for t in detect_trends(s, f)],
            "policy_usage": metrics.policy_usage(s, f),
        }

    return await db.run_sync(build)


def _warnings(complaint: Complaint) -> list[str]:
    warnings: list[str] = []
    level = complaint.escalation_level or 0
    if level:
        names = {lv.level: lv.name for lv in analysis_config().escalation_levels}
        warnings.append(f"Escalation level {level}: {names.get(level, 'escalated')}")
    if complaint.sla_status == "breached":
        warnings.append("SLA breached")
    elif complaint.sla_status == "at_risk":
        warnings.append("SLA at risk")
    if complaint.needs_review:
        warnings.append("Awaiting manual review")
    warnings += [text for key, text in WARNING_SIGNALS.items() if key in complaint.signals]
    return warnings


def _agent_item(complaint: Complaint, run: AnalysisRun | None) -> AgentQueueItem:
    output = run.output if run and run.output else {}
    draft = output.get("customer_response", {}).get("body")
    return AgentQueueItem(
        complaint_ref=complaint.complaint_ref,
        title=complaint.title,
        created_at=complaint.created_at,
        status=complaint.status,
        category_code=complaint.category_code,
        subcategory_code=complaint.subcategory_code,
        department_code=complaint.department_code,
        priority=complaint.priority,
        urgency=complaint.urgency,
        sentiment=complaint.sentiment,
        escalation_level=complaint.escalation_level,
        verification=complaint.verification,
        needs_review=complaint.needs_review,
        sla_status=complaint.sla_status,
        resolution_due_at=complaint.resolution_due_at,
        summary=output.get("complaint_summary"),
        recommended_steps=[step["description"] for step in output.get("resolution_steps", [])],
        suggested_response=complaint.approved_response or draft,
        response_approved=complaint.approved_response is not None,
        escalation_warnings=_warnings(complaint),
    )


@router.get("/dashboard/agent", response_model=AgentDashboardOut)
async def agent_dashboard(
    department: str | None = Query(None, description="Defaults to the agent's own department"),
    user: User = Depends(staff),
    db: AsyncSession = Depends(get_db),
) -> AgentDashboardOut:
    code = department or (user.department.code if user.department else None)
    rows = await db.run_sync(lambda s: metrics.agent_queue(s, code))
    return AgentDashboardOut(department=code, items=[_agent_item(c, r) for c, r in rows])


@router.get("/reports", response_model=list[ReportSpecOut])
async def list_reports(_: User = Depends(insight_roles)) -> list[ReportSpecOut]:
    return [
        ReportSpecOut(code=s.code, title=s.title, description=s.description)
        for s in REPORTS.values()
    ]


async def _report(db: AsyncSession, code: str, f: Filters) -> Report:
    if code not in REPORTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown report")
    return await db.run_sync(lambda s: build_report(s, code, f))


@router.get("/reports/{code}", response_model=ReportOut)
async def preview_report(
    code: str,
    f: Filters = Depends(analytics_filters),
    _: User = Depends(insight_roles),
    db: AsyncSession = Depends(get_db),
) -> ReportOut:
    """The report as JSON; each table is cut to its first 100 rows (exports have them all)."""
    report = await _report(db, code, f)
    return ReportOut.model_validate(
        {
            "code": report.code,
            "title": report.title,
            "description": report.description,
            "generated_at": report.generated_at,
            "filters": [{"label": k, "value": v} for k, v in report.filters],
            "summary": [{"label": k, "value": cell(v) or None} for k, v in report.summary],
            "tables": [
                {
                    "title": t.title,
                    "columns": [{"key": k, "header": h} for k, h in t.columns],
                    "rows": [
                        {k: cell(r.get(k)) for k, _ in t.columns} for r in t.rows[:PREVIEW_ROWS]
                    ],
                    "total_rows": len(t.rows),
                }
                for t in report.tables
            ],
        }
    )


@router.get(
    "/reports/{code}/export",
    response_class=Response,
    responses={200: {"content": {e.media_type: {} for e in EXPORTERS.values()}}},
)
async def export_report(
    code: str,
    format: str = Query("csv", pattern="^(csv|xlsx|pdf)$"),
    f: Filters = Depends(analytics_filters),
    _: User = Depends(insight_roles),
    db: AsyncSession = Depends(get_db),
) -> Response:
    report = await _report(db, code, f)
    exporter = EXPORTERS[format]
    filename = f"{report.code}_{report.generated_at:%Y%m%d_%H%M}.{exporter.extension}"
    return Response(
        exporter.render(report),
        media_type=exporter.media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
