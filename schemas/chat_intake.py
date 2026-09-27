"""Structured output of one support-chat intake turn (gathering complaint details)."""

from pydantic import Field

from schemas.complaint_analysis import Strict

SCHEMA_NAME = "chat_intake_turn.v1"


class IntakeTurn(Strict):
    reply: str = Field(
        description="The next message to the customer: one short question, or a "
        "one-sentence summary lead-in when ready_to_confirm is true"
    )
    title: str = Field(description="Short complaint title in plain words (max 80 characters)")
    missing: list[str] = Field(description="Essential details still missing")
    ready_to_confirm: bool = Field(
        description="True when what happened, the product or order, "
        "and what the customer wants are known"
    )
    requested_resolution: str | None = Field(
        description="What the customer asks for, in their terms, or null if not stated"
    )
