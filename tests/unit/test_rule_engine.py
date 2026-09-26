from typing import Any

import pytest

from complaint_rules.conditions import ConditionError, compile_condition
from complaint_rules.engine import Decision, Issue, RuleSpec, decide
from complaint_rules.matrix import read_default_matrix


@pytest.fixture(scope="module")
def rules() -> list[RuleSpec]:
    return [RuleSpec.from_record(r) for r in read_default_matrix()]


def run(rules: list[RuleSpec], issues: list[tuple[str, str | None]], **facts: Any) -> Decision:
    return decide(rules, [Issue(c, s) for c, s in issues], facts)


class TestConditions:
    def test_boolean_logic_and_comparisons(self) -> None:
        condition = compile_condition("days_late > 5 and shipping_method == 'standard'")
        assert condition.evaluate({"days_late": 6, "shipping_method": "standard"})
        assert not condition.evaluate({"days_late": 5, "shipping_method": "standard"})
        assert condition.facts == {"days_late", "shipping_method"}

    def test_membership_and_negation(self) -> None:
        condition = compile_condition("'SAFETY' in issue_categories and not has_order")
        assert condition.evaluate({"issue_categories": ["DELIVERY", "SAFETY"], "has_order": False})

    def test_missing_fact_never_matches_a_comparison(self) -> None:
        assert not compile_condition("days_late > 5").evaluate({})
        assert not compile_condition("days_late <= 5").evaluate({})

    def test_empty_condition_always_matches(self) -> None:
        assert compile_condition("").evaluate({})

    @pytest.mark.parametrize(
        "source",
        [
            "__import__('os').system('ls')",
            "order_amount.real > 1",
            "[x for x in issue_categories]",
            "order_amount + 1 > 2",
            "lambda: True",
        ],
    )
    def test_code_is_rejected(self, source: str) -> None:
        with pytest.raises(ConditionError):
            compile_condition(source)

    def test_unknown_fact_is_rejected(self) -> None:
        with pytest.raises(ConditionError, match="Unknown fact"):
            compile_condition("days_lat > 5")


class TestRuleMatrix:
    def test_matrix_meets_srs_minimums(self) -> None:
        records = read_default_matrix()
        assert len(records) >= 100
        assert sum(r.rule_type == "escalation" for r in records) >= 30

    def test_most_specific_rule_wins(self, rules: list[RuleSpec]) -> None:
        decision = run(
            rules,
            [("DELIVERY", "DELAYED_DELIVERY")],
            has_order=True,
            days_late=7,
            shipping_method="standard",
        )
        assert decision.resolution_rules == ["DEL-003"]
        assert "CHECK_COMPENSATION_ELIGIBILITY" in decision.required_actions
        assert "PROMISE_CASH_COMPENSATION" in decision.prohibited_actions
        assert (decision.department, decision.priority) == ("LOGISTICS", "P2")

    def test_unknown_subcategory_falls_back_to_category_default(
        self, rules: list[RuleSpec]
    ) -> None:
        decision = run(rules, [("DELIVERY", "DRONE_DELIVERY_FAILED")])
        assert decision.resolution_rules == ["DEL-000"]
        assert decision.department == "LOGISTICS"

    def test_brand_new_category_uses_fallback_department(self, rules: list[RuleSpec]) -> None:
        decision = run(rules, [("SUSTAINABILITY", "EXCESS_PACKAGING")])
        assert decision.unmatched_issues == ["SUSTAINABILITY/EXCESS_PACKAGING"]
        assert decision.department == "CUSTOMER_RELATIONS"


class TestSrsTraps:
    def test_calm_safety_complaint_is_critical_whatever_the_category(
        self, rules: list[RuleSpec]
    ) -> None:
        # Classified as a plain product defect, written calmly, but the lexicon saw "swelling".
        decision = run(
            rules,
            [("PRODUCT_DEFECT", "MALFUNCTION_AFTER_USE")],
            safety_hazard=True,
            emotional_intensity=False,
            days_since_delivery=40,
        )
        assert (decision.priority, decision.urgency, decision.escalation_level) == (
            "P0",
            "Critical",
            5,
        )
        assert decision.department == "PRODUCT_SAFETY"
        assert "WARRANTY" in decision.supporting_departments
        assert "ESC-001" in decision.escalation_rules
        assert "ADVISE_STOP_USING_PRODUCT" in decision.required_actions

    def test_furious_but_low_risk_complaint_stays_low(self, rules: list[RuleSpec]) -> None:
        decision = run(rules, [("TECHNICAL_SUPPORT", "SETUP_ASSISTANCE")], emotional_intensity=True)
        assert (decision.priority, decision.escalation_level) == ("P3", 0)

    def test_vip_with_minor_issue_is_not_prioritised(self, rules: list[RuleSpec]) -> None:
        decision = run(
            rules,
            [("TECHNICAL_SUPPORT", "CONNECTIVITY_ISSUE")],
            customer_type="VIP",
            is_vip=True,
        )
        assert decision.priority == "P3"

    def test_low_value_privacy_breach_is_critical(self, rules: list[RuleSpec]) -> None:
        decision = run(
            rules, [("BILLING", "INCORRECT_CHARGE")], privacy_exposure=True, disputed_amount=4.99
        )
        assert (decision.priority, decision.escalation_level) == ("P0", 4)
        assert decision.department == "PRIVACY_COMPLIANCE"
        assert "BILLING" in decision.supporting_departments

    def test_legal_threat_goes_to_compliance_review(self, rules: list[RuleSpec]) -> None:
        decision = run(rules, [("REFUND", "REFUND_DELAY")], legal_threat=True)
        assert decision.escalation_level == 4
        assert "DISCUSS_LIABILITY" in decision.prohibited_actions
        assert decision.department == "RETURNS"  # legal threat adds compliance, keeps owner

    def test_third_complaint_escalates_to_manager(self, rules: list[RuleSpec]) -> None:
        decision = run(rules, [("REFUND", "REFUND_DELAY")], repeat_count=2)
        assert decision.escalation_level >= 2
        assert decision.priority == "P1"

    def test_multi_issue_complaint_routes_to_most_severe_department(
        self, rules: list[RuleSpec]
    ) -> None:
        decision = run(
            rules,
            [("DELIVERY", "DAMAGED_IN_TRANSIT"), ("REFUND", "REFUND_DELAY")],
            has_order=True,
            days_since_delivery=1,
        )
        assert decision.resolution_rules == ["DEL-009", "REF-001"]
        assert decision.department == "RETURNS"
        assert "LOGISTICS" in decision.supporting_departments

    def test_prompt_injection_triggers_human_review(self, rules: list[RuleSpec]) -> None:
        decision = run(
            rules, [("REFUND", "REFUND_DENIED")], prompt_injection=True, days_since_delivery=90
        )
        assert "ESC-015" in decision.escalation_rules
        assert "GRANT_POLICY_EXCEPTION" in decision.prohibited_actions
