"""Post Pipeline 2 outcomes and reviewer-approved replies into the complaint's chat.

Each reply text is posted at most once, and at most one holding message per conversation, so
re-validation never repeats itself in the chat.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from database.models import ChatConversation, ChatMessage, Complaint

AUTO_REPLY_VERDICTS = {"verified", "corrected"}


def _holding_text(complaint: Complaint) -> str:
    due = complaint.first_response_due_at
    when = f" by {due.astimezone(UTC):%d %b, %H:%M} UTC" if due else " shortly"
    return (
        f"A specialist is reviewing your complaint {complaint.complaint_ref}. "
        f"We'll reply here{when}."
    )


def after_validation(
    db: Session, complaint: Complaint, verdict: str, draft: str | None, *, auto_reply: bool = True
) -> None:
    conversation = db.scalar(
        select(ChatConversation).where(ChatConversation.complaint_id == complaint.id)
    )
    if conversation is None:
        return
    posted = set(
        db.scalars(select(ChatMessage.kind).where(ChatMessage.conversation_id == conversation.id))
    )
    replies = set(
        db.scalars(
            select(ChatMessage.content).where(
                ChatMessage.conversation_id == conversation.id, ChatMessage.kind == "reply"
            )
        )
    )
    if replies or complaint.approved_response:
        return  # the customer already has a reply; re-validation never adds another
    if auto_reply and verdict in AUTO_REPLY_VERDICTS and draft:
        db.add(
            ChatMessage(
                conversation_id=conversation.id,
                role="assistant",
                kind="reply",
                content=draft,
                payload={"verdict": verdict},
            )
        )
    elif (verdict not in AUTO_REPLY_VERDICTS or not auto_reply) and "holding" not in posted:
        db.add(
            ChatMessage(
                conversation_id=conversation.id,
                role="assistant",
                kind="holding",
                content=_holding_text(complaint),
                payload={"verdict": verdict},
            )
        )


async def after_approval(db: AsyncSession, complaint: Complaint) -> None:
    if not complaint.approved_response:
        return
    conversation = await db.scalar(
        select(ChatConversation).where(ChatConversation.complaint_id == complaint.id)
    )
    if conversation is None:
        return
    already = await db.scalar(
        select(ChatMessage.id).where(
            ChatMessage.conversation_id == conversation.id,
            ChatMessage.kind == "reply",
            ChatMessage.content == complaint.approved_response,
        )
    )
    if already is None:
        db.add(
            ChatMessage(
                conversation_id=conversation.id,
                role="assistant",
                kind="reply",
                content=complaint.approved_response,
                payload={"approved_at": datetime.now(UTC).isoformat()},
            )
        )
