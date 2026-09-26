"""Typed access to the controlled vocabularies in `config/` (analysis values, actions,
risk-signal lexicons). Loaded once per process; restart workers after editing YAML."""

from functools import lru_cache
from typing import Any

import yaml
from pydantic import BaseModel

from src.core.config import ROOT_DIR

CONFIG_DIR = ROOT_DIR / "config"


def _load(name: str) -> Any:
    with (CONFIG_DIR / name).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


class EscalationLevel(BaseModel):
    level: int
    code: str
    name: str


class AnalysisConfig(BaseModel):
    sentiments: list[str]
    emotions: list[str]
    urgencies: list[str]
    priorities: list[str]
    escalation_levels: list[EscalationLevel]
    response_tones: list[str]
    response_types: list[str]
    follow_up_types: list[str]
    compensation_types: list[str]
    policy_applicability: list[str]
    complaint_channels: list[str]

    @property
    def escalation_codes(self) -> list[str]:
        return [level.code for level in self.escalation_levels]

    def escalation_level(self, code: str) -> int:
        return next(level.level for level in self.escalation_levels if level.code == code)


class Action(BaseModel):
    code: str
    kind: str
    description: str


class Signal(BaseModel):
    description: str
    patterns: list[str]


@lru_cache
def analysis_config() -> AnalysisConfig:
    return AnalysisConfig.model_validate(_load("analysis.yaml"))


@lru_cache
def actions() -> dict[str, Action]:
    return {a["code"]: Action.model_validate(a) for a in _load("actions.yaml")["actions"]}


@lru_cache
def signal_lexicons() -> dict[str, Signal]:
    return {k: Signal.model_validate(v) for k, v in _load("detectors.yaml")["signals"].items()}


@lru_cache
def organization() -> dict[str, Any]:
    data: dict[str, Any] = _load("organization.yaml")
    return data


@lru_cache
def analytics_config() -> dict[str, Any]:
    """SLA monitoring, trend detection and dashboard settings (`config/analytics.yaml`)."""
    data: dict[str, Any] = _load("analytics.yaml")
    return data
