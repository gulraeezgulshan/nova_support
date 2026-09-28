"""Accuracy is only scored against labels that actually contain the field."""

from comparison_engine.report import field_accuracy


def fields(**values: tuple[str, str]) -> dict[str, dict[str, str]]:
    return {f: {"genai": g, "python": p} for f, (g, p) in values.items()}


def test_fields_missing_from_a_label_are_not_counted_as_wrong() -> None:
    complaints = [
        # hold-out style label: category only
        (fields(category=("DELIVERY", "DELIVERY"), department=("LOGISTICS", "LOGISTICS")),
         {"category": "DELIVERY"}),
        # dataset style label: category and department
        (fields(category=("BILLING", "REFUND"), department=("BILLING", "BILLING")),
         {"category": "REFUND", "department": "BILLING"}),
    ]  # fmt: skip
    genai, python, labelled = field_accuracy(complaints, ("category", "department"))
    assert labelled == {"category": 2, "department": 1}
    assert genai == {"category": 0.5, "department": 1.0}
    assert python == {"category": 1.0, "department": 1.0}


def test_a_field_nobody_labelled_has_no_accuracy() -> None:
    genai, python, labelled = field_accuracy(
        [(fields(urgency=("High", "Critical")), {"category": "SAFETY"})], ("urgency",)
    )
    assert labelled == {"urgency": 0} and genai == {} and python == {}
