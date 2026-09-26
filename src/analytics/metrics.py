"""Complaint analytics (SRS Steps 63-64): KPIs, distributions, volume over time, resolution
time, department performance, repeat complaints, SLA risks, policy usage, GenAI/Python
agreement and manual reviews.

Functions take a synchronous session; the async API calls them through `db.run_sync`, and
the report CLI uses them directly.
"""

import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from sqlalchemy import (
    Integer,
    Select,
    case,
    cast,
    func,
    literal,
    or_,
    select,
)
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from database.models import (
    AnalysisRun,
    Category,
    Complaint,
    ComplaintStatus,
    Customer,
    Department,
    Order,
    ReviewerDecision,
    ReviewStatus,
    ReviewTask,
    RunStatus,
    Subcategory,
    ValidationRun,
)
from src.analytics.filters import Filters

CLOSED = [ComplaintStatus.RESOLVED.value, ComplaintStatus.CLOSED.value]
UNCLASSIFIED = "UNCLASSIFIED"

# Repeat complaint: linked to an earlier complaint (named, near-duplicate or reworded
# repeat) or saying so in its own words.
IS_REPEAT = or_(
    Complaint.previous_complaint_id.is_not(None),
    Complaint.related_complaint_id.is_not(None),
    Complaint.duplicate_of_id.is_not(None),
    Complaint.signals.has_key("repeat_contact"),
)
IS_ESCALATED = func.coalesce(Complaint.escalation_level, 0) >= 1
RESOLUTION_HOURS = func.extract("epoch", Complaint.resolved_at - Complaint.created_at) / 3600
PRODUCT = func.coalesce(Order.product_category, literal("UNKNOWN"))

DIMENSIONS: dict[str, Any] = {
    "category": func.coalesce(Complaint.category_code, UNCLASSIFIED),
    "subcategory": func.coalesce(Complaint.subcategory_code, UNCLASSIFIED),
    "department": func.coalesce(Complaint.department_code, "UNASSIGNED"),
    "priority": func.coalesce(Complaint.priority, "NONE"),
    "urgency": func.coalesce(Complaint.urgency, "NONE"),
    "sentiment": func.coalesce(Complaint.sentiment, "NONE"),
    "status": Complaint.status,
    "escalation_level": func.coalesce(Complaint.escalation_level, 0),
    "verification": func.coalesce(Complaint.verification, "not_validated"),
    "sla_status": Complaint.sla_status,
    "channel": Complaint.channel,
    "product": PRODUCT,
    "customer_type": Customer.customer_type,
}


def scoped(f: Filters, *columns: Any) -> Select[Any]:
    """A select over complaints (customer and order joined), restricted by the filters."""
    stmt = (
        select(*columns)
        .select_from(Complaint)
        .join(Customer, Complaint.customer_id == Customer.id)
        .outerjoin(Order, Complaint.order_id == Order.id)
    )
    return f.apply(stmt)


def _pct(part: float, whole: float) -> float | None:
    return round(100 * part / whole, 1) if whole else None


def _round(value: Any, digits: int = 1) -> float | None:
    return None if value is None else round(float(value), digits)


def labels(db: Session) -> dict[str, dict[str, str]]:
    """Display names for codes (categories, subcategories, departments)."""
    return {
        "category": dict(db.execute(select(Category.code, Category.name)).all()),
        "subcategory": dict(db.execute(select(Subcategory.code, Subcategory.name)).all()),
        "department": dict(db.execute(select(Department.code, Department.name)).all()),
    }


def _label(names: dict[str, dict[str, str]], dimension: str, key: Any) -> str:
    text = str(key)
    if dimension == "escalation_level":
        return f"L{key}" if key else "None"
    if dimension == "priority":
        return text
    return names.get(dimension, {}).get(text) or text.replace("_", " ").capitalize()


# --- KPIs --------------------------------------------------------------------------


def _latest_validations(f: Filters) -> Select[Any]:
    """The latest validation run of each complaint that has a GenAI analysis."""
    return (
        scoped(f, ValidationRun)
        .join(ValidationRun, ValidationRun.complaint_id == Complaint.id)
        .where(ValidationRun.analysis_run_id.is_not(None))
        .ext(distinct_on(ValidationRun.complaint_id))
        .order_by(ValidationRun.complaint_id, ValidationRun.created_at.desc())
    )


def overview(db: Session, f: Filters) -> dict[str, Any]:
    open_ = Complaint.status.not_in(CLOSED)
    row = db.execute(
        scoped(
            f,
            func.count().label("total"),
            func.count().filter(open_).label("open"),
            func.count().filter(Complaint.status.in_(CLOSED)).label("resolved"),
            func.count().filter(IS_ESCALATED).label("escalated"),
            func.count().filter(IS_ESCALATED, open_).label("open_escalated"),
            func.count().filter(Complaint.category_code.is_(None)).label("unclassified"),
            func.count().filter(Complaint.needs_review).label("needs_review"),
            func.count().filter(Complaint.sla_status == "at_risk").label("sla_at_risk"),
            func.count().filter(Complaint.sla_status == "breached").label("sla_breached"),
            func.count().filter(Complaint.sla_status == "met").label("sla_met"),
            func.count().filter(Complaint.sla_status == "missed").label("sla_missed"),
            func.count().filter(IS_REPEAT).label("repeat"),
            func.count().filter(Complaint.verification == "verified").label("verified"),
            func.count().filter(Complaint.verification == "corrected").label("corrected"),
            func.count().filter(Complaint.verification == "needs_review").label("flagged"),
            func.avg(RESOLUTION_HOURS).label("avg_resolution_hours"),
        )
    ).one()
    data = dict(row._mapping)
    data["avg_resolution_hours"] = _round(data["avg_resolution_hours"])
    data["sla_compliance_pct"] = _pct(data["sla_met"], data["sla_met"] + data["sla_missed"])
    comparison = genai_python(db, f)
    data["analysed"] = comparison["compared"]
    data["mismatches"] = comparison["mismatched"]
    data["open_reviews"] = db.scalar(
        scoped(f, func.count())
        .join(ReviewTask, ReviewTask.complaint_id == Complaint.id)
        .where(ReviewTask.status == ReviewStatus.OPEN)
    )
    return data


# --- distributions and volume -----------------------------------------------------------


def distribution(db: Session, f: Filters, dimension: str) -> list[dict[str, Any]]:
    column = DIMENSIONS[dimension]
    rows = db.execute(
        scoped(f, column.label("key"), func.count().label("n"))
        .group_by(column)
        .order_by(func.count().desc())
    ).all()
    names = labels(db)
    total = sum(r.n for r in rows)
    return [
        {
            "key": str(r.key),
            "label": _label(names, dimension, r.key),
            "count": r.n,
            "pct": _pct(r.n, total),
        }
        for r in rows
    ]


def volume(db: Session, f: Filters, bucket: str = "day") -> list[dict[str, Any]]:
    if bucket not in {"day", "week", "month"}:
        raise ValueError("bucket must be day, week or month")
    period = func.date_trunc(bucket, Complaint.created_at).label("period")
    rows = db.execute(
        scoped(
            f,
            period,
            func.count().label("total"),
            func.count().filter(IS_ESCALATED).label("escalated"),
            func.count().filter(IS_REPEAT).label("repeat"),
            func.count().filter(Complaint.status.in_(CLOSED)).label("resolved"),
        )
        .group_by(period)
        .order_by(period)
    ).all()
    return [
        {
            "period": r.period.date().isoformat(),
            "total": r.total,
            "escalated": r.escalated,
            "repeat": r.repeat,
            "resolved": r.resolved,
        }
        for r in rows
    ]


# --- resolution, departments, escalations, repeats ------------------------------------


def resolution_time(db: Session, f: Filters) -> list[dict[str, Any]]:
    rows = db.execute(
        scoped(
            f,
            Complaint.priority,
            func.count().label("resolved"),
            func.avg(RESOLUTION_HOURS).label("avg_hours"),
            func.percentile_cont(0.5).within_group(RESOLUTION_HOURS).label("median_hours"),
            func.count().filter(Complaint.sla_status == "met").label("met"),
        )
        .where(Complaint.resolved_at.is_not(None), Complaint.priority.is_not(None))
        .group_by(Complaint.priority)
        .order_by(Complaint.priority)
    ).all()
    return [
        {
            "priority": r.priority,
            "resolved": r.resolved,
            "avg_hours": _round(r.avg_hours),
            "median_hours": _round(r.median_hours),
            "within_sla_pct": _pct(r.met, r.resolved),
        }
        for r in rows
    ]


def department_performance(db: Session, f: Filters) -> list[dict[str, Any]]:
    dept = func.coalesce(Complaint.department_code, "UNASSIGNED")
    open_ = Complaint.status.not_in(CLOSED)
    rows = db.execute(
        scoped(
            f,
            dept.label("department"),
            func.count().label("total"),
            func.count().filter(open_).label("open"),
            func.count().filter(Complaint.status.in_(CLOSED)).label("resolved"),
            func.count().filter(IS_ESCALATED).label("escalated"),
            func.count().filter(Complaint.needs_review).label("in_review"),
            func.count().filter(Complaint.sla_status == "at_risk").label("at_risk"),
            func.count().filter(Complaint.sla_status == "breached").label("breached"),
            func.count().filter(Complaint.sla_status == "met").label("met"),
            func.count().filter(Complaint.sla_status == "missed").label("missed"),
            func.avg(RESOLUTION_HOURS).label("avg_hours"),
            func.count().filter(IS_REPEAT).label("repeat"),
        )
        .group_by(dept)
        .order_by(func.count().desc())
    ).all()
    names = labels(db)["department"]
    return [
        {
            "department": r.department,
            "label": names.get(r.department, r.department.replace("_", " ").capitalize()),
            "total": r.total,
            "open": r.open,
            "resolved": r.resolved,
            "escalated": r.escalated,
            "in_review": r.in_review,
            "at_risk": r.at_risk,
            "breached": r.breached,
            "repeat": r.repeat,
            "avg_resolution_hours": _round(r.avg_hours),
            "sla_compliance_pct": _pct(r.met, r.met + r.missed),
        }
        for r in rows
    ]


def complaint_rows(
    db: Session, f: Filters, *conditions: Any, order: Any = None, limit: int | None = None
) -> list[dict[str, Any]]:
    """Complaint listing used by the report tables and dashboard lists."""
    stmt = scoped(
        f,
        Complaint.complaint_ref,
        Customer.customer_ref,
        Complaint.created_at,
        Complaint.title,
        Complaint.category_code,
        Complaint.subcategory_code,
        Complaint.department_code,
        Complaint.priority,
        Complaint.urgency,
        Complaint.sentiment,
        Complaint.escalation_level,
        Complaint.status,
        Complaint.verification,
        Complaint.sla_status,
        Complaint.resolution_due_at,
        Complaint.resolved_at,
        PRODUCT.label("product"),
        Complaint.needs_review,
    ).where(*conditions)
    orders = order if isinstance(order, tuple) else (order,)
    stmt = (
        stmt.order_by(*orders) if order is not None else stmt.order_by(Complaint.created_at.desc())
    )
    if limit:
        stmt = stmt.limit(limit)
    return [dict(r._mapping) for r in db.execute(stmt).all()]


def sla_risks(db: Session, f: Filters, limit: int | None = 10) -> list[dict[str, Any]]:
    return complaint_rows(
        db,
        f,
        Complaint.sla_status.in_(["at_risk", "breached"]),
        order=Complaint.resolution_due_at.asc().nulls_last(),
        limit=limit,
    )


def escalations(db: Session, f: Filters) -> list[dict[str, Any]]:
    return complaint_rows(
        db, f, IS_ESCALATED, order=(Complaint.escalation_level.desc(), Complaint.created_at.desc())
    )


def repeat_complaints(db: Session, f: Filters) -> list[dict[str, Any]]:
    return complaint_rows(db, f, IS_REPEAT)


# --- GenAI vs Python ---------------------------------------------------------------

COMPARED_FIELDS = ("category", "department", "urgency", "priority", "escalation_level")


def genai_python(db: Session, f: Filters, include_rows: bool = False) -> dict[str, Any]:
    runs = db.scalars(_latest_validations(f)).all()
    agree: Counter[str] = Counter()
    mismatched_rows: list[dict[str, Any]] = []
    refs = (
        dict(
            db.execute(
                select(Complaint.id, Complaint.complaint_ref).where(
                    Complaint.id.in_([r.complaint_id for r in runs])
                )
            )
            .tuples()
            .all()
        )
        if include_rows and runs
        else {}
    )
    rows: list[dict[str, Any]] = []
    for run in runs:
        by_field = {row["field"]: row for row in run.comparison}
        diffs = [r for r in run.comparison if not r["match"]]
        for name in COMPARED_FIELDS:
            agree[name] += bool(by_field.get(name, {}).get("match"))
        if include_rows:
            row = {
                "complaint_ref": refs.get(run.complaint_id),
                "verdict": run.verdict,
                "score": run.score,
                **{f"genai_{n}": by_field.get(n, {}).get("genai") for n in COMPARED_FIELDS},
                **{f"python_{n}": by_field.get(n, {}).get("python") for n in COMPARED_FIELDS},
                "policy_refs": " ".join(run.python_decision.get("policy_refs", [])),
                "match": not diffs,
                "explanation": " | ".join(f"{d['field']}: {d['explanation']}" for d in diffs),
            }
            rows.append(row)
            if diffs:
                mismatched_rows.append(row)
    n = len(runs)
    return {
        "compared": n,
        "mismatched": sum(any(not r["match"] for r in run.comparison) for run in runs),
        "verdicts": dict(Counter(run.verdict for run in runs)),
        "agreement_pct": {name: _pct(agree[name], n) for name in COMPARED_FIELDS},
        "rows": rows,
        "mismatches": mismatched_rows,
    }


# --- policy usage ------------------------------------------------------------------


def policy_usage(db: Session, f: Filters) -> list[dict[str, Any]]:
    """How often each document is retrieved, cited by the GenAI and required by the rules."""
    latest_runs = (
        scoped(f, AnalysisRun)
        .join(AnalysisRun, AnalysisRun.complaint_id == Complaint.id)
        .where(AnalysisRun.status == RunStatus.COMPLETED)
        .ext(distinct_on(AnalysisRun.complaint_id))
        .order_by(AnalysisRun.complaint_id, AnalysisRun.created_at.desc())
    )
    usage: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"retrieved": 0, "cited": 0, "required_by_rules": 0, "versions": set()}
    )
    for run in db.scalars(latest_runs):
        for doc in {(p["doc_code"], p.get("version")) for p in run.retrieved_policies}:
            usage[doc[0]]["retrieved"] += 1
            if doc[1]:
                usage[doc[0]]["versions"].add(str(doc[1]))
        for code in {ref["doc_code"] for ref in (run.output or {}).get("policy_references", [])}:
            usage[code]["cited"] += 1
    in_scope = scoped(f, Complaint.id).scalar_subquery()
    latest_validations = (
        select(ValidationRun)
        .where(ValidationRun.complaint_id.in_(in_scope))
        .ext(distinct_on(ValidationRun.complaint_id))
        .order_by(ValidationRun.complaint_id, ValidationRun.created_at.desc())
    )
    for validation in db.scalars(latest_validations):
        required = validation.python_decision.get("policy_refs", [])
        for code in {ref.split("#")[0] for ref in required}:
            usage[code]["required_by_rules"] += 1
    return sorted(
        (
            {
                "doc_code": code,
                "retrieved": data["retrieved"],
                "cited": data["cited"],
                "required_by_rules": data["required_by_rules"],
                "versions": ", ".join(sorted(data["versions"])),
            }
            for code, data in usage.items()
        ),
        key=lambda r: (-r["cited"], -r["retrieved"], r["doc_code"]),
    )


# --- manual reviews ----------------------------------------------------------------


@dataclass
class ReviewSummary:
    open: int
    resolved: int
    avg_hours_to_resolve: float | None
    decisions: dict[str, int]
    top_reasons: list[dict[str, Any]]
    tasks: list[dict[str, Any]]


def manual_reviews(db: Session, f: Filters, include_tasks: bool = False) -> ReviewSummary:
    in_scope = scoped(f, Complaint.id).scalar_subquery()
    tasks = db.execute(
        select(ReviewTask, Complaint.complaint_ref, Complaint.category_code)
        .join(Complaint, Complaint.id == ReviewTask.complaint_id)
        .where(ReviewTask.complaint_id.in_(in_scope))
        .order_by(ReviewTask.created_at.desc())
    ).all()
    decisions = db.execute(
        select(ReviewerDecision.action, func.count())
        .where(ReviewerDecision.complaint_id.in_(in_scope))
        .group_by(ReviewerDecision.action)
    ).all()
    reasons: Counter[str] = Counter()
    hours: list[float] = []
    for task, _, _ in tasks:
        reasons.update({reason.split(":")[0].strip()[:80] for reason in task.reasons})
        if task.resolved_at:
            hours.append((task.resolved_at - task.created_at).total_seconds() / 3600)
    return ReviewSummary(
        open=sum(t.status == ReviewStatus.OPEN for t, _, _ in tasks),
        resolved=sum(t.status == ReviewStatus.RESOLVED for t, _, _ in tasks),
        avg_hours_to_resolve=_round(sum(hours) / len(hours)) if hours else None,
        decisions={str(action): count for action, count in decisions},
        top_reasons=[{"reason": r, "count": c} for r, c in reasons.most_common(10)],
        tasks=[
            {
                "complaint_ref": ref,
                "category": category,
                "status": task.status,
                "priority": task.priority,
                "opened_at": task.created_at,
                "resolved_at": task.resolved_at,
                "reasons": "; ".join(task.reasons),
            }
            for task, ref, category in tasks
        ]
        if include_tasks
        else [],
    )


def resolution_compliance(db: Session, f: Filters) -> dict[str, Any]:
    """Were resolutions made the way the rules require? Validation outcome, reviewer sign-off
    where required, and SLA."""
    closed = Complaint.status.in_(CLOSED)
    row = db.execute(
        scoped(
            f,
            func.count().filter(closed).label("resolved"),
            func.count()
            .filter(closed, Complaint.verification.in_(["verified", "corrected"]))
            .label("validated"),
            func.count()
            .filter(closed, Complaint.approved_response.is_not(None))
            .label("approved_response"),
            func.count().filter(closed, Complaint.needs_review).label("closed_while_flagged"),
            func.count().filter(closed, Complaint.sla_status == "met").label("within_sla"),
            func.count().filter(closed, Complaint.sla_status == "missed").label("sla_missed"),
            func.count()
            .filter(
                closed,
                cast(func.coalesce(Complaint.escalation_level, 0), Integer) >= 4,
                Complaint.approved_response.is_(None),
            )
            .label("sensitive_without_signoff"),
        )
    ).one()
    data = dict(row._mapping)
    data["within_sla_pct"] = _pct(data["within_sla"], data["within_sla"] + data["sla_missed"])
    data["validated_pct"] = _pct(data["validated"], data["resolved"])
    data["rows"] = complaint_rows(db, f, closed)
    return data


def agent_queue(
    db: Session, department_code: str | None, limit: int = 50
) -> list[tuple[Complaint, AnalysisRun | None]]:
    """Open complaints for an agent's department (all departments when none is set),
    most urgent SLA first, with the latest completed GenAI analysis."""
    stmt = select(Complaint).where(Complaint.status.not_in(CLOSED))
    if department_code:
        stmt = stmt.where(
            or_(
                Complaint.department_code == department_code,
                Complaint.supporting_departments.contains([department_code]),
            )
        )
    order = case(
        (Complaint.sla_status == "breached", 0),
        (Complaint.sla_status == "at_risk", 1),
        else_=2,
    )
    complaints = (
        db.scalars(
            stmt.order_by(order, Complaint.priority.asc().nulls_last(), Complaint.created_at).limit(
                limit
            )
        )
        .unique()
        .all()
    )
    ids: list[uuid.UUID] = [c.id for c in complaints]
    runs = {
        run.complaint_id: run
        for run in db.scalars(
            select(AnalysisRun)
            .where(AnalysisRun.complaint_id.in_(ids), AnalysisRun.status == RunStatus.COMPLETED)
            .ext(distinct_on(AnalysisRun.complaint_id))
            .order_by(AnalysisRun.complaint_id, AnalysisRun.created_at.desc())
        )
    }
    return [(c, runs.get(c.id)) for c in complaints]
