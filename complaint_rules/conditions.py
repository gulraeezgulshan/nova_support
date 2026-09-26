"""A small, safe condition language for rules.

Examples:
    days_late > 5 and shipping_method == 'standard'
    safety_hazard or 'SAFETY' in issue_categories
    order_amount > 1000 and (requests_refund or requests_compensation)

The text is parsed with Python's `ast` module and only a whitelist of node types is
accepted: and/or/not, comparisons (== != < <= > >= in, not in), fact names, and literal
strings, numbers, booleans and lists. Nothing is ever passed to `eval`.

A missing fact (None) makes any comparison involving it False, so a rule about delivery
delays simply doesn't match a complaint without an order.
"""

import ast
import operator
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from complaint_rules.facts import FACTS

_COMPARATORS: dict[type[ast.cmpop], Callable[[Any, Any], bool]] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}


class ConditionError(ValueError):
    """The condition text is not valid rule syntax."""


@dataclass(frozen=True)
class Condition:
    source: str
    tree: ast.expr | None  # None = always true
    facts: frozenset[str]

    def evaluate(self, facts: Mapping[str, Any]) -> bool:
        if self.tree is None:
            return True
        return bool(_eval(self.tree, facts))


def compile_condition(source: str, known_facts: Mapping[str, object] = FACTS) -> Condition:
    text = (source or "").strip()
    if not text:
        return Condition("", None, frozenset())
    try:
        tree = ast.parse(text, mode="eval").body
    except SyntaxError as exc:
        raise ConditionError(f"Invalid syntax: {exc.msg}") from exc
    names = _validate(tree)
    unknown = sorted(names - set(known_facts))
    if unknown:
        raise ConditionError(f"Unknown fact(s): {', '.join(unknown)}")
    return Condition(text, tree, frozenset(names))


def _validate(node: ast.AST) -> set[str]:
    """Reject anything outside the whitelist; return the fact names used."""
    if isinstance(node, ast.BoolOp):
        return set().union(*(_validate(v) for v in node.values))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return _validate(node.operand)
    if isinstance(node, ast.Compare):
        for op in node.ops:
            if type(op) not in _COMPARATORS:
                raise ConditionError(f"Operator {type(op).__name__} is not allowed")
        return _validate(node.left).union(*(_validate(c) for c in node.comparators))
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, int, float, bool)):
        return set()
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, ast.USub)
        and isinstance(node.operand, ast.Constant)
        and isinstance(node.operand.value, (int, float))
    ):
        return set()
    if isinstance(node, (ast.List, ast.Tuple)):
        for element in node.elts:
            if not (isinstance(element, ast.Constant) and isinstance(element.value, (str, int))):
                raise ConditionError("Lists may only contain literal strings or numbers")
        return set()
    raise ConditionError(f"'{ast.unparse(node)}' is not allowed in a rule condition")


def _eval(node: ast.expr, facts: Mapping[str, Any]) -> Any:
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            return all(_eval(v, facts) for v in node.values)
        return any(_eval(v, facts) for v in node.values)
    if isinstance(node, ast.UnaryOp):
        value = _eval(node.operand, facts)
        if isinstance(node.op, ast.USub):
            return -value
        return not value
    if isinstance(node, ast.Compare):
        left = _eval(node.left, facts)
        for op, comparator in zip(node.ops, node.comparators, strict=True):
            right = _eval(comparator, facts)
            if left is None or right is None:
                return False
            try:
                if not _COMPARATORS[type(op)](left, right):
                    return False
            except TypeError:  # e.g. comparing text with a number: treat as not matching
                return False
            left = right
        return True
    if isinstance(node, ast.Name):
        return facts.get(node.id)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_eval(e, facts) for e in node.elts]
    raise ConditionError(f"Cannot evaluate {ast.dump(node)}")  # unreachable after validation
