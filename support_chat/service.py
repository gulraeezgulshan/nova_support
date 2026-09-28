"""Support-chat conversation state machine: gathering -> confirming -> submitted.

The complaint is filed through the normal intake (`submit_complaint`, channel `live_chat`)
with a description made only of the customer's own messages.
"""

import uuid
from functools import partial
from typing import Any

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from complaint_processing.preprocessing import sanitize_text
from complaint_processing.sensitive import redact
from complaint_processing.service import (
    MAX_DESCRIPTION_CHARS,
    ComplaintInput,
    ComplaintValidationError,
    DuplicateComplaintError,
    enqueue_automatic,
    get_or_create_customer,
    submit_complaint,
)
from database.models import (
    ChatConversation,
    ChatMessage,
    ChatState,
    Complaint,
    ComplaintEvent,
    Customer,
    Order,
    User,
)
from genai_pipeline.providers import LLMProvider, get_provider
from src.core.config import get_settings
from support_chat.intake import Role, next_turn

MAX_MESSAGE_CHARS = 2000
MAX_CUSTOMER_MESSAGES = 30
GREETING = "Hi, I'm the VoltHaven support assistant. Which order is this about?"
ASK_WHAT_HAPPENED = "Sorry to hear there's a problem with your {product}. What happened?"
ACKNOWLEDGEMENT = "Thanks, I've added this to your complaint {ref}. Our team will see it."


class ChatError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def intake_provider() -> LLMProvider | None:
    """The configured GenAI provider, or None when no API key is set (fixed questions)."""
    return get_provider() if get_settings().genai_api_key else None


def _order_dict(order: Order | None) -> dict[str, str] | None:
    if order is None:
        return None
    return {
        "order_ref": order.order_ref,
        "product_name": order.product_name,
        "order_date": str(order.order_date),
        "committed_delivery_date": str(order.committed_delivery_date),
        "status": order.status,
    }


def _add(
    db: AsyncSession,
    conversation: ChatConversation,
    role: str,
    content: str,
    kind: str = "text",
    payload: dict[str, Any] | None = None,
) -> None:
    db.add(
        ChatMessage(
            conversation_id=conversation.id,
            role=role,
            kind=kind,
            content=content,
            payload=payload or {},
        )
    )


async def _customer(db: AsyncSession, user: User) -> Customer:
    return await get_or_create_customer(db, user)


async def _own_order(db: AsyncSession, customer: Customer, order_ref: str) -> Order:
    order = await db.scalar(
        select(Order).where(Order.order_ref == order_ref.upper(), Order.customer_id == customer.id)
    )
    if order is None:
        raise ChatError(404, "Order not found")
    return order


async def start_conversation(
    db: AsyncSession, user: User, order_ref: str | None, new: bool = False
) -> ChatConversation:
    """Resume the latest conversation about this order (or about no order), including one
    already submitted so its reply stays reachable; `new` closes an unfinished one and starts
    over."""
    customer = await _customer(db, user)
    order = await _own_order(db, customer, order_ref) if order_ref else None
    stmt = select(ChatConversation).where(
        ChatConversation.customer_id == customer.id,
        ChatConversation.state != ChatState.CLOSED,
    )
    stmt = (
        stmt.where(ChatConversation.order_id == order.id)
        if order
        else stmt.where(ChatConversation.order_id.is_(None))
    )
    existing = await db.scalar(stmt.order_by(ChatConversation.created_at.desc()).limit(1))
    if existing is not None and not new:
        return existing
    if existing is not None and existing.state in (ChatState.GATHERING, ChatState.CONFIRMING):
        existing.state = ChatState.CLOSED
    conversation = ChatConversation(
        customer_id=customer.id, user_id=user.id, order_id=order.id if order else None
    )
    db.add(conversation)
    await db.flush()
    if order is not None:
        _add(db, conversation, "assistant", ASK_WHAT_HAPPENED.format(product=order.product_name))
    else:
        recent = (
            await db.scalars(
                select(Order)
                .where(Order.customer_id == customer.id)
                .order_by(Order.order_date.desc())
                .limit(5)
            )
        ).all()
        _add(
            db,
            conversation,
            "assistant",
            GREETING,
            "order_options",
            {
                "orders": [
                    {
                        "order_ref": o.order_ref,
                        "product_name": o.product_name,
                        "order_date": str(o.order_date),
                        "status": o.status,
                    }
                    for o in recent
                ]
            },
        )
    await db.commit()
    return conversation


async def load_conversation(
    db: AsyncSession, user: User, conversation_id: uuid.UUID
) -> ChatConversation:
    # populate_existing: a rollback during confirm expires cached rows; always read fresh.
    conversation = await db.get(ChatConversation, conversation_id, populate_existing=True)
    if conversation is None or conversation.user_id != user.id:
        raise ChatError(404, "Conversation not found")
    return conversation


async def select_order(
    db: AsyncSession, conversation: ChatConversation, order_ref: str | None
) -> None:
    if conversation.state != ChatState.GATHERING:
        raise ChatError(409, "The order can only be chosen before the complaint is summarised.")
    customer = await db.get(Customer, conversation.customer_id)
    assert customer is not None
    order = await _own_order(db, customer, order_ref) if order_ref else None
    conversation.order_id = order.id if order else None
    product = order.product_name if order else "order"
    _add(db, conversation, "assistant", ASK_WHAT_HAPPENED.format(product=product))
    await db.commit()


async def _customer_texts(db: AsyncSession, conversation: ChatConversation) -> list[str]:
    return list(
        (
            await db.scalars(
                select(ChatMessage.content)
                .where(
                    ChatMessage.conversation_id == conversation.id,
                    ChatMessage.role == "customer",
                    ChatMessage.kind == "text",
                )
                .order_by(ChatMessage.id)
            )
        ).all()
    )


async def _history(db: AsyncSession, conversation: ChatConversation) -> list[tuple[Role, str]]:
    """The conversation so far (the customer's words and the assistant's questions), in order."""
    rows = await db.execute(
        select(ChatMessage.role, ChatMessage.content)
        .where(
            ChatMessage.conversation_id == conversation.id,
            or_(
                and_(ChatMessage.role == "customer", ChatMessage.kind == "text"),
                ChatMessage.role == "assistant",
            ),
        )
        .order_by(ChatMessage.id)
    )
    return [("customer" if role == "customer" else "assistant", text) for role, text in rows]


async def post_customer_message(
    db: AsyncSession, conversation: ChatConversation, text: str, provider: LLMProvider | None
) -> None:
    if len(text) > MAX_MESSAGE_CHARS:
        raise ChatError(422, f"Messages are limited to {MAX_MESSAGE_CHARS} characters.")
    if conversation.customer_messages >= MAX_CUSTOMER_MESSAGES:
        raise ChatError(422, "This conversation has reached its message limit.")
    if conversation.state in (ChatState.CLOSED, ChatState.SUBMITTING):
        raise ChatError(409, "This conversation is closed or being submitted.")
    clean = redact(sanitize_text(text)).text
    if not clean:
        raise ChatError(422, "The message is empty.")
    conversation.customer_messages += 1

    if conversation.state == ChatState.SUBMITTED:
        _add(db, conversation, "customer", clean, "note")
        complaint = await db.get(Complaint, conversation.complaint_id)
        assert complaint is not None
        db.add(
            ComplaintEvent(
                complaint_id=complaint.id,
                event_type="customer_message",
                message=f"Customer message (chat): {clean}",
                customer_visible=True,
                actor_user_id=conversation.user_id,
            )
        )
        _add(
            db,
            conversation,
            "assistant",
            ACKNOWLEDGEMENT.format(ref=complaint.complaint_ref),
            "acknowledgement",
        )
        await db.commit()
        return

    earlier = await _customer_texts(db, conversation)
    if sum(len(t) + 1 for t in earlier) + len(clean) > MAX_DESCRIPTION_CHARS:
        raise ChatError(
            422,
            f"Your messages are too long in total for one complaint ({MAX_DESCRIPTION_CHARS} "
            "characters). Please start over with a shorter description.",
        )
    conversation.state = ChatState.GATHERING  # a message while confirming = "change something"
    _add(db, conversation, "customer", clean)
    await db.flush()
    texts = await _customer_texts(db, conversation)
    order = await db.get(Order, conversation.order_id) if conversation.order_id else None
    result = await run_in_threadpool(
        partial(
            next_turn,
            provider,
            order=_order_dict(order),
            customer_messages=texts,
            history=await _history(db, conversation),
        )
    )
    conversation.draft = {
        "title": result.title,
        "requested_resolution": result.requested_resolution,
    }
    if result.ready:
        conversation.state = ChatState.CONFIRMING
        _add(
            db,
            conversation,
            "assistant",
            result.reply,
            "summary",
            {
                "title": result.title,
                "description": "\n".join(texts),
                "order_ref": order.order_ref if order else None,
                "requested_resolution": result.requested_resolution,
                "intake": result.details,
                "source": result.source,
            },
        )
    else:
        _add(
            db,
            conversation,
            "assistant",
            result.reply,
            "text",
            {"intake": result.details, "source": result.source},
        )
    await db.commit()


async def _claim(db: AsyncSession, conversation_id: uuid.UUID) -> bool:
    """Atomically move confirming -> submitting, so only one confirm request proceeds."""
    result = await db.execute(
        update(ChatConversation)
        .where(
            ChatConversation.id == conversation_id, ChatConversation.state == ChatState.CONFIRMING
        )
        .values(state=ChatState.SUBMITTING)
    )
    await db.commit()
    return bool(result.rowcount)  # type: ignore[attr-defined]


async def _reopen(db: AsyncSession, conversation_id: uuid.UUID, user: User, message: str) -> None:
    await db.rollback()
    await db.refresh(user)  # the rollback expired the signed-in user's row
    conversation = await db.get(ChatConversation, conversation_id, populate_existing=True)
    assert conversation is not None
    conversation.state = ChatState.GATHERING
    _add(db, conversation, "assistant", message)
    await db.commit()


async def confirm(db: AsyncSession, conversation: ChatConversation, user: User) -> None:
    conversation_id = conversation.id
    if not await _claim(db, conversation_id):
        raise ChatError(409, "There is no summary waiting for confirmation.")
    claimed = await db.get(ChatConversation, conversation_id, populate_existing=True)
    assert claimed is not None
    customer = await db.get(Customer, claimed.customer_id)
    order = await db.get(Order, claimed.order_id) if claimed.order_id else None
    assert customer is not None
    texts = await _customer_texts(db, claimed)
    draft = claimed.draft or {}
    data = ComplaintInput(
        title=str(draft.get("title") or texts[0][:80]),
        description="\n".join(texts),
        order_ref=order.order_ref if order else None,
        channel="live_chat",
        requested_resolution=draft.get("requested_resolution"),
    )
    try:
        # Queued only after the chat is linked, so the reply always finds the conversation.
        complaint = await submit_complaint(
            db, customer=customer, data=data, submitted_by=user, enqueue=False
        )
    except ComplaintValidationError as exc:
        too_short = any("too short" in issue.lower() for issue in exc.issues)
        await _reopen(
            db,
            conversation_id,
            user,
            "I need a little more detail before I can send this. Could you tell me more about "
            "what happened?"
            if too_short
            else "I couldn't send this yet: " + " ".join(exc.issues),
        )
        return
    except DuplicateComplaintError as exc:
        await _reopen(db, conversation_id, user, str(exc))
        raise ChatError(409, str(exc)) from exc
    submitted = await db.get(ChatConversation, conversation_id, populate_existing=True)
    assert submitted is not None
    submitted.complaint_id = complaint.id
    submitted.state = ChatState.SUBMITTED
    _add(
        db,
        submitted,
        "assistant",
        f"Thanks, I've sent this to our team. Your complaint reference is "
        f"{complaint.complaint_ref}. I'll post the reply here as soon as it's ready. "
        "You can add photos or documents to it from My complaints.",
        "reference",
        {"complaint_ref": complaint.complaint_ref},
    )
    complaint_id, user_id = complaint.id, user.id
    await db.commit()
    enqueue_automatic(complaint_id, user_id)


async def messages_after(
    db: AsyncSession, conversation_id: uuid.UUID, after: int = 0
) -> list[ChatMessage]:
    return list(
        (
            await db.scalars(
                select(ChatMessage)
                .where(ChatMessage.conversation_id == conversation_id, ChatMessage.id > after)
                .order_by(ChatMessage.id)
            )
        ).all()
    )
