"""The classifier's thresholds and signal boosts come from the Settings page."""

import app_settings
from python_validation.classifier import classify

TAXONOMY = {
    "DELIVERY": ["DELAYED_DELIVERY", "LOST_PARCEL"],
    "SAFETY": ["OVERHEATING_BATTERY", "INJURY_REPORTED"],
}


def with_validation(**fields: object) -> None:
    app_settings.override(app_settings.load({"validation": fields}))


def test_confident_threshold_from_settings() -> None:
    text = "where is my order"  # one decisive phrase: score 3 for DELAYED_DELIVERY
    assert classify(text, {}, TAXONOMY).confidence == "confident"
    with_validation(classifier_confident=6)
    assert classify(text, {}, TAXONOMY).confidence == "tentative"


def test_boost_weight_from_settings() -> None:
    signals = {"safety_hazard": ["sparked"]}
    default = classify("", signals, TAXONOMY).candidates[0]
    assert (default.subcategory, default.score) == ("OVERHEATING_BATTERY", 3)
    boosts = app_settings.defaults().validation.model_dump()["signal_boosts"]
    boosts["safety_hazard"]["weight"] = 5
    with_validation(signal_boosts=boosts)
    assert classify("", signals, TAXONOMY).candidates[0].score == 5


def test_boost_to_inactive_subcategory_is_skipped() -> None:
    taxonomy = {"DELIVERY": ["DELAYED_DELIVERY"], "SAFETY": ["INJURY_REPORTED"]}
    result = classify("", {"safety_hazard": ["sparked"]}, taxonomy)
    assert result.candidates == []
