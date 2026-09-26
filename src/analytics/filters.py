"""Filters shared by the dashboards, analytics and reports.

Adding a dashboard filter (a live-modification task in the SRS) means adding one field here,
one clause in `apply`, and one query parameter in `src/api/routes/analytics.py`.
"""

from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import Select

from database.models import Complaint


@dataclass(frozen=True)
class Filters:
    date_from: date | None = None
    date_to: date | None = None  # inclusive
    category: str | None = None
    department: str | None = None
    priority: str | None = None
    sentiment: str | None = None
    channel: str | None = None
    source: str | None = None  # portal | dataset | evaluation

    def apply[T: Select[Any]](self, stmt: T) -> T:
        if self.date_from:
            stmt = stmt.where(Complaint.created_at >= datetime.combine(self.date_from, time(), UTC))
        if self.date_to:
            end = datetime.combine(self.date_to + timedelta(days=1), time(), UTC)
            stmt = stmt.where(Complaint.created_at < end)
        if self.category:
            stmt = stmt.where(Complaint.category_code == self.category)
        if self.department:
            stmt = stmt.where(Complaint.department_code == self.department)
        if self.priority:
            stmt = stmt.where(Complaint.priority == self.priority)
        if self.sentiment:
            stmt = stmt.where(Complaint.sentiment == self.sentiment)
        if self.channel:
            stmt = stmt.where(Complaint.channel == self.channel)
        if self.source:
            stmt = stmt.where(Complaint.source == self.source)
        return stmt

    def describe(self) -> list[tuple[str, str]]:
        """Human-readable list of the active filters (printed on exported reports)."""
        return [
            (name.replace("_", " ").capitalize(), str(value))
            for name, value in asdict(self).items()
            if value not in (None, "")
        ]
