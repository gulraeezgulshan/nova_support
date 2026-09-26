"""The controlled values the model must choose from, assembled from the live taxonomy
(database) and `config/`. Adding a category or department in the admin UI changes the
vocabulary, the JSON schema and the prompt on the next analysis, with no code change."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Category, Department, SlaPolicy
from src.core.domain import actions, analysis_config


@dataclass(frozen=True)
class Vocabulary:
    categories: dict[str, list[str]]  # category code -> subcategory codes (active only)
    category_names: dict[str, str]
    subcategory_names: dict[str, str]
    departments: dict[str, str]  # code -> name
    priorities: dict[str, str]  # P0 -> "Critical (resolve within 4 h)"
    actions: dict[str, str]  # code -> description
    sentiments: list[str]
    emotions: list[str]
    urgencies: list[str]
    escalation_levels: dict[str, str]  # code -> name
    response_tones: list[str]
    response_types: list[str]
    follow_up_types: list[str]
    compensation_types: list[str]
    policy_applicability: list[str]

    @property
    def all_subcategories(self) -> list[str]:
        return sorted({s for subs in self.categories.values() for s in subs})


def load_vocabulary(db: Session) -> Vocabulary:
    config = analysis_config()
    categories = db.scalars(select(Category).where(Category.is_active).order_by(Category.code))
    category_map: dict[str, list[str]] = {}
    category_names: dict[str, str] = {}
    subcategory_names: dict[str, str] = {}
    for category in categories:
        category_names[category.code] = category.name
        category_map[category.code] = []
        for sub in category.subcategories:
            if sub.is_active:
                category_map[category.code].append(sub.code)
                subcategory_names[sub.code] = sub.name
    departments = {
        d.code: d.name
        for d in db.scalars(
            select(Department).where(Department.is_active).order_by(Department.code)
        )
    }
    priorities = {
        s.priority: f"{s.name} (first response {s.first_response_minutes} min, "
        f"resolution {s.resolution_minutes // 60} h)"
        for s in db.scalars(select(SlaPolicy).order_by(SlaPolicy.priority))
    }
    return Vocabulary(
        categories=category_map,
        category_names=category_names,
        subcategory_names=subcategory_names,
        departments=departments,
        priorities=priorities,
        actions={code: a.description for code, a in actions().items()},
        sentiments=config.sentiments,
        emotions=config.emotions,
        urgencies=config.urgencies,
        escalation_levels={lvl.code: lvl.name for lvl in config.escalation_levels},
        response_tones=config.response_tones,
        response_types=config.response_types,
        follow_up_types=config.follow_up_types,
        compensation_types=config.compensation_types,
        policy_applicability=config.policy_applicability,
    )
