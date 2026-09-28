"""Automatic replies off: verified complaints wait for a reviewer; sender name from Settings."""

from database.models import OutboundEmail
from email_channel.tasks import build_message
from python_validation.pipeline import AUTO_REPLIES_OFF, review_reasons
from src.core.config import get_settings
from tests.fixtures.settings import use_settings


def test_review_reasons_follow_the_setting() -> None:
    assert review_reasons("verified", [], auto_replies=True) is None
    assert review_reasons("corrected", ["fixed priority"], auto_replies=True) is None
    assert review_reasons("verified", [], auto_replies=False) == [AUTO_REPLIES_OFF]
    assert review_reasons("needs_review", ["unsupported promise"], auto_replies=False) == [
        "unsupported promise"
    ]


def test_sender_name_comes_from_settings() -> None:
    use_settings(email={"from_name": "Nova Support Desk"})
    email = OutboundEmail(
        to_address="sara@example.test",
        kind="reply",
        subject="Re: Cracked screen [CMP-000001]",
        body="Hello",
        message_id="<m1@volthaven.test>",
    )
    assert build_message(email, get_settings())["From"].startswith("Nova Support Desk")
