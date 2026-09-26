"""Reports (SRS Step 67 and deliverable 9, the Complaint Intelligence Report).

Each report is a title, a summary (metric/value pairs) and one or more tables, built from
the analytics queries; `src/analytics/export.py` renders it as CSV, Excel or PDF.

    uv run python -m src.analytics.reports complaint_intelligence --format pdf xlsx
    uv run python -m src.analytics.reports --list
"""

import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from database.models import Complaint
from src.analytics import metrics as m
from src.analytics.filters import Filters
from src.analytics.trends import detect_trends

Columns = list[tuple[str, str]]  # (row key, column header)


@dataclass
class Table:
    title: str
    columns: Columns
    rows: list[dict[str, Any]]
    note: str | None = None


@dataclass
class Report:
    code: str
    title: str
    description: str
    generated_at: datetime
    filters: list[tuple[str, str]]
    summary: list[tuple[str, Any]] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)


@dataclass(frozen=True)
class ReportSpec:
    code: str
    title: str
    description: str
    build: Callable[[Session, Filters], tuple[list[tuple[str, Any]], list[Table]]]


COMPLAINT_COLUMNS: Columns = [
    ("complaint_ref", "Complaint"),
    ("created_at", "Submitted"),
    ("customer_ref", "Customer"),
    ("category_code", "Category"),
    ("subcategory_code", "Subcategory"),
    ("product", "Product"),
    ("department_code", "Department"),
    ("priority", "Priority"),
    ("urgency", "Urgency"),
    ("sentiment", "Sentiment"),
    ("escalation_level", "Escalation"),
    ("status", "Status"),
    ("verification", "Verification"),
    ("sla_status", "SLA"),
]
SLA_COLUMNS: Columns = [
    ("complaint_ref", "Complaint"),
    ("priority", "Priority"),
    ("department_code", "Department"),
    ("status", "Status"),
    ("created_at", "Submitted"),
    ("resolution_due_at", "Resolution due"),
    ("sla_status", "SLA"),
]
DISTRIBUTION_COLUMNS: Columns = [
    ("label", "Value"),
    ("key", "Code"),
    ("count", "Complaints"),
    ("pct", "Share %"),
]
DEPARTMENT_COLUMNS: Columns = [
    ("label", "Department"),
    ("total", "Total"),
    ("open", "Open"),
    ("resolved", "Resolved"),
    ("escalated", "Escalated"),
    ("in_review", "In review"),
    ("repeat", "Repeat"),
    ("at_risk", "SLA at risk"),
    ("breached", "SLA breached"),
    ("avg_resolution_hours", "Avg resolution (h)"),
    ("sla_compliance_pct", "SLA compliance %"),
]
POLICY_COLUMNS: Columns = [
    ("doc_code", "Document"),
    ("versions", "Versions retrieved"),
    ("retrieved", "Retrieved"),
    ("cited", "Cited by GenAI"),
    ("required_by_rules", "Required by rules"),
]
COMPARISON_COLUMNS: Columns = [
    ("complaint_ref", "Complaint"),
    ("genai_category", "GenAI category"),
    ("python_category", "Python category"),
    ("genai_department", "GenAI department"),
    ("python_department", "Python department"),
    ("genai_urgency", "GenAI urgency"),
    ("python_urgency", "Python urgency"),
    ("genai_escalation_level", "GenAI escalation"),
    ("python_escalation_level", "Python escalation"),
    ("policy_refs", "Policy references"),
    ("match", "Match"),
    ("verdict", "Verification"),
    ("explanation", "Explanation"),
]
REVIEW_COLUMNS: Columns = [
    ("complaint_ref", "Complaint"),
    ("category", "Category"),
    ("priority", "Priority"),
    ("status", "Review status"),
    ("opened_at", "Opened"),
    ("resolved_at", "Resolved"),
    ("reasons", "Reasons"),
]
TREND_COLUMNS: Columns = [
    ("label", "Trend"),
    ("kind", "Type"),
    ("current", "Last window"),
    ("previous", "Window before"),
    ("change_pct", "Change %"),
    ("message", "Detail"),
]


def _dist(db: Session, f: Filters, dimension: str, title: str) -> Table:
    return Table(title, DISTRIBUTION_COLUMNS, m.distribution(db, f, dimension))


def _kpis(db: Session, f: Filters) -> list[tuple[str, Any]]:
    o = m.overview(db, f)
    return [
        ("Total complaints", o["total"]),
        ("Open", o["open"]),
        ("Resolved or closed", o["resolved"]),
        ("Escalated", o["escalated"]),
        ("Repeat complaints", o["repeat"]),
        ("SLA at risk", o["sla_at_risk"]),
        ("SLA breached", o["sla_breached"]),
        ("SLA compliance %", o["sla_compliance_pct"]),
        ("Average resolution time (hours)", o["avg_resolution_hours"]),
        ("Analysed by GenAI and validated", o["analysed"]),
        ("GenAI/Python mismatches", o["mismatches"]),
        ("Open manual reviews", o["open_reviews"]),
        ("Awaiting classification", o["unclassified"]),
    ]


def complaint_intelligence(db: Session, f: Filters) -> tuple[list[tuple[str, Any]], list[Table]]:
    comparison = m.genai_python(db, f, include_rows=True)
    reviews = m.manual_reviews(db, f, include_tasks=True)
    tables = [
        _dist(db, f, "category", "Category distribution"),
        _dist(db, f, "priority", "Priority distribution"),
        _dist(db, f, "sentiment", "Sentiment distribution"),
        Table("Department routing", DEPARTMENT_COLUMNS, m.department_performance(db, f)),
        _dist(db, f, "escalation_level", "Escalations by level"),
        Table("Escalated complaints", COMPLAINT_COLUMNS, m.escalations(db, f)),
        Table("Repeat complaints", COMPLAINT_COLUMNS, m.repeat_complaints(db, f)),
        _dist(db, f, "sla_status", "SLA status"),
        Table("SLA risks (at risk or breached)", SLA_COLUMNS, m.sla_risks(db, f, limit=None)),
        Table("Policy usage", POLICY_COLUMNS, m.policy_usage(db, f)),
        Table("GenAI/Python disagreements", COMPARISON_COLUMNS, comparison["mismatches"]),
        Table("Manual-review cases", REVIEW_COLUMNS, reviews.tasks),
        Table("Trends", TREND_COLUMNS, [t.to_dict() for t in detect_trends(db, f)]),
    ]
    return _kpis(db, f), tables


def complaint_analysis(db: Session, f: Filters) -> tuple[list[tuple[str, Any]], list[Table]]:
    tables = [
        Table("Complaints", COMPLAINT_COLUMNS, m.complaint_rows(db, f)),
        _dist(db, f, "category", "By category"),
        _dist(db, f, "product", "By product line"),
        _dist(db, f, "urgency", "By urgency"),
        _dist(db, f, "channel", "By channel"),
        Table(
            "Volume by week",
            [
                ("period", "Week starting"),
                ("total", "Complaints"),
                ("escalated", "Escalated"),
                ("repeat", "Repeat"),
                ("resolved", "Resolved"),
            ],
            m.volume(db, f, "week"),
        ),
    ]
    return _kpis(db, f), tables


def department_performance(db: Session, f: Filters) -> tuple[list[tuple[str, Any]], list[Table]]:
    rows = m.department_performance(db, f)
    resolution = m.resolution_time(db, f)
    tables = [
        Table("Department performance", DEPARTMENT_COLUMNS, rows),
        Table(
            "Resolution time by priority",
            [
                ("priority", "Priority"),
                ("resolved", "Resolved"),
                ("avg_hours", "Average (h)"),
                ("median_hours", "Median (h)"),
                ("within_sla_pct", "Within SLA %"),
            ],
            resolution,
        ),
    ]
    return [("Departments", len(rows)), *_kpis(db, f)[:4]], tables


def escalations(db: Session, f: Filters) -> tuple[list[tuple[str, Any]], list[Table]]:
    rows = m.escalations(db, f)
    return [("Escalated complaints", len(rows))], [
        _dist(db, f, "escalation_level", "Escalations by level"),
        Table("Escalated complaints", COMPLAINT_COLUMNS, rows),
    ]


def sla_status(db: Session, f: Filters) -> tuple[list[tuple[str, Any]], list[Table]]:
    o = m.overview(db, f)
    running = m.complaint_rows(
        db,
        f,
        Complaint.sla_status.in_(["on_track", "at_risk", "breached"]),
        order=Complaint.resolution_due_at.asc(),
    )
    return [
        ("SLA at risk", o["sla_at_risk"]),
        ("SLA breached", o["sla_breached"]),
        ("Resolved within SLA", o["sla_met"]),
        ("Resolved after SLA", o["sla_missed"]),
        ("SLA compliance %", o["sla_compliance_pct"]),
    ], [
        _dist(db, f, "sla_status", "SLA status"),
        Table("Open complaints with a running SLA", SLA_COLUMNS, running),
        Table(
            "Resolution time by priority",
            [
                ("priority", "Priority"),
                ("resolved", "Resolved"),
                ("avg_hours", "Average (h)"),
                ("median_hours", "Median (h)"),
                ("within_sla_pct", "Within SLA %"),
            ],
            m.resolution_time(db, f),
        ),
    ]


def policy_usage(db: Session, f: Filters) -> tuple[list[tuple[str, Any]], list[Table]]:
    rows = m.policy_usage(db, f)
    return [("Documents used", len(rows))], [Table("Policy usage", POLICY_COLUMNS, rows)]


def resolution_compliance(db: Session, f: Filters) -> tuple[list[tuple[str, Any]], list[Table]]:
    data = m.resolution_compliance(db, f)
    return [
        ("Resolved or closed", data["resolved"]),
        ("Validated (verified or corrected) %", data["validated_pct"]),
        ("With an approved customer response", data["approved_response"]),
        ("Closed while still flagged for review", data["closed_while_flagged"]),
        ("Sensitive (level 4+) closed without sign-off", data["sensitive_without_signoff"]),
        ("Resolved within SLA %", data["within_sla_pct"]),
    ], [Table("Resolved complaints", COMPLAINT_COLUMNS, data["rows"])]


def genai_python_comparison(db: Session, f: Filters) -> tuple[list[tuple[str, Any]], list[Table]]:
    data = m.genai_python(db, f, include_rows=True)
    summary: list[tuple[str, Any]] = [
        ("Complaints compared", data["compared"]),
        ("With at least one mismatch", data["mismatched"]),
        *[(f"Verdict: {k}", v) for k, v in sorted(data["verdicts"].items())],
        *[(f"Agreement % ({k})", v) for k, v in data["agreement_pct"].items()],
    ]
    return summary, [Table("GenAI vs Python", COMPARISON_COLUMNS, data["rows"])]


def manual_reviews(db: Session, f: Filters) -> tuple[list[tuple[str, Any]], list[Table]]:
    data = m.manual_reviews(db, f, include_tasks=True)
    return [
        ("Open reviews", data.open),
        ("Resolved reviews", data.resolved),
        ("Average hours to resolve", data.avg_hours_to_resolve),
    ], [
        Table("Review cases", REVIEW_COLUMNS, data.tasks),
        Table(
            "Reviewer decisions",
            [("action", "Action"), ("count", "Decisions")],
            [{"action": k, "count": v} for k, v in data.decisions.items()],
        ),
        Table(
            "Most common review reasons",
            [("reason", "Reason"), ("count", "Cases")],
            data.top_reasons,
        ),
    ]


REPORTS: dict[str, ReportSpec] = {
    spec.code: spec
    for spec in [
        ReportSpec(
            "complaint_intelligence",
            "Complaint Intelligence Report",
            "Distributions, routing, escalations, repeats, SLA risk, policy usage, "
            "GenAI/Python disagreements, manual reviews and trends.",
            complaint_intelligence,
        ),
        ReportSpec(
            "complaint_analysis",
            "Complaint Analysis",
            "Every complaint with its classification, plus volume and breakdowns.",
            complaint_analysis,
        ),
        ReportSpec(
            "department_performance",
            "Department Performance",
            "Workload, escalations, SLA compliance and resolution time per department.",
            department_performance,
        ),
        ReportSpec("escalations", "Escalations", "Escalated complaints by level.", escalations),
        ReportSpec(
            "sla_status",
            "SLA Status",
            "Running SLAs, risks, breaches and resolution time against target.",
            sla_status,
        ),
        ReportSpec(
            "policy_usage",
            "Policy Usage",
            "Documents retrieved, cited by the GenAI and required by the rules.",
            policy_usage,
        ),
        ReportSpec(
            "resolution_compliance",
            "Resolution Compliance",
            "Whether resolved complaints were validated, signed off and on time.",
            resolution_compliance,
        ),
        ReportSpec(
            "genai_python_comparison",
            "GenAI / Python Comparison",
            "Field-by-field agreement between the GenAI and the Python rules.",
            genai_python_comparison,
        ),
        ReportSpec(
            "manual_reviews",
            "Manual Reviews",
            "Review cases, reasons and reviewer decisions.",
            manual_reviews,
        ),
    ]
}


def build_report(db: Session, code: str, f: Filters) -> Report:
    spec = REPORTS[code]
    summary, tables = spec.build(db, f)
    return Report(
        code=spec.code,
        title=spec.title,
        description=spec.description,
        generated_at=datetime.now(UTC),
        filters=f.describe(),
        summary=summary,
        tables=tables,
    )


def main() -> int:
    from database.session import sync_session
    from src.analytics.export import EXPORTERS
    from src.core.config import ROOT_DIR

    parser = argparse.ArgumentParser(description="Generate a report into reports/")
    parser.add_argument("code", nargs="?", choices=sorted(REPORTS))
    parser.add_argument("--format", nargs="+", default=["pdf"], choices=sorted(EXPORTERS))
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    if args.list or not args.code:
        for spec in REPORTS.values():
            print(f"  {spec.code:<26} {spec.description}")
        return 0
    with sync_session() as db:
        report = build_report(db, args.code, Filters())
    for fmt in args.format:
        exporter = EXPORTERS[fmt]
        path = ROOT_DIR / "reports" / f"{report.code}.{exporter.extension}"
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(exporter.render(report))
        print(f"Wrote {path.relative_to(ROOT_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
