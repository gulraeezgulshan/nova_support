"""Results of the Patterns page tests (also the API response shapes)."""

from pydantic import BaseModel


class CandidateOut(BaseModel):
    category: str
    subcategory: str
    score: int


class ClassificationOut(BaseModel):
    status: str  # confident | tentative | unknown
    primary: str | None  # "CATEGORY/SUBCATEGORY"
    candidates: list[CandidateOut]


class SentenceOut(BaseModel):
    sentence: str
    commitment: bool
    conditional: bool
    kinds: list[str]


class TextSide(BaseModel):
    signals: dict[str, list[str]]
    classification: ClassificationOut
    sentences: list[SentenceOut]


class TextTestOut(BaseModel):
    saved: TextSide
    draft: TextSide


class DatasetHit(BaseModel):
    dataset_id: str
    phrases: list[str]


class SignalDelta(BaseModel):
    signal: str
    saved: int
    draft: int
    gained: list[DatasetHit]
    lost: list[DatasetHit]


class ClassifierCompare(BaseModel):
    saved_correct: int
    draft_correct: int
    saved_confident: int
    draft_confident: int
    right_to_wrong: list[str]
    wrong_to_right: list[str]


class Compare(BaseModel):
    saved: int
    draft: int
    total: int


class Hits(BaseModel):
    true_positive: int
    false_positive: int


class InjectionCompare(BaseModel):
    saved: Hits
    draft: Hits


class DatasetCheckOut(BaseModel):
    total: int
    signals: list[SignalDelta]
    classifier: ClassifierCompare
    escalation: Compare
    urgency: Compare
    prompt_injection: InjectionCompare
