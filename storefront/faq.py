"""FAQ answers with policy placeholders such as {standard_days} (Settings → Shop).

Answers are stored with their placeholders and filled from the policy numbers when shown, so
an FAQ never disagrees with the delivery, returns and warranty facts.
"""

from string import Formatter

from storefront.config import storefront_config


def policy_values() -> dict[str, int]:
    c = storefront_config()
    return {**c.shipping.model_dump(), **c.returns.model_dump(), **c.warranty.model_dump()}


def placeholder_problem(text: str) -> str | None:
    """Why this answer cannot be filled, or None."""
    known = policy_values()
    try:
        fields = [name for _, name, _, _ in Formatter().parse(text) if name is not None]
    except ValueError:
        return "braces must wrap a placeholder name"
    for name in fields:
        if not name.strip() or name.isdigit():
            return "braces must wrap a placeholder name"
        if name not in known:
            options = ", ".join(f"{{{k}}}" for k in sorted(known))
            return f"unknown placeholder {{{name}}}; use one of {options}"
    return None


def filled(answer: str) -> str:
    return answer.format(**policy_values())
