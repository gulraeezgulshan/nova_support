"""Support chat endpoints (customers) and the transcript for staff."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import ChatConversation, ChatMessage, Complaint, Order, User
from database.session import get_db
from security.dependencies import STAFF_ROLES, get_current_user, require_roles
from src.api.schemas import (
    ChatConversationOut,
    ChatMessageIn,
    ChatMessageOut,
    ChatOrderIn,
    ChatStartIn,
)
from support_chat import service

router = APIRouter(tags=["chat"])


async def _out(db: AsyncSession, conversation: ChatConversation) -> ChatConversationOut:
    order_ref = (
        await db.scalar(select(Order.order_ref).where(Order.id == conversation.order_id))
        if conversation.order_id
        else None
    )
    complaint_ref = (
        await db.scalar(
            select(Complaint.complaint_ref).where(Complaint.id == conversation.complaint_id)
        )
        if conversation.complaint_id
        else None
    )
    messages = await service.messages_after(db, conversation.id)
    return ChatConversationOut(
        id=conversation.id,
        state=conversation.state,
        order_ref=order_ref,
        complaint_ref=complaint_ref,
        recent_complaint_ref=await service.recent_complaint(db, conversation),
        messages=[_for_customer(m) for m in messages],
    )


def _for_customer(message: ChatMessage) -> ChatMessageOut:
    """Customers see the conversation, not internal details (provider, model, errors)."""
    out = ChatMessageOut.model_validate(message)
    out.payload = {k: v for k, v in out.payload.items() if k != "intake"}
    return out


def _raise(exc: service.ChatError) -> HTTPException:
    return HTTPException(exc.status, exc.message)


@router.post("/chat/conversations", response_model=ChatConversationOut)
async def start_chat(
    payload: ChatStartIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> ChatConversationOut:
    try:
        conversation = await service.start_conversation(db, user, payload.order_ref, payload.new)
    except service.ChatError as exc:
        raise _raise(exc) from exc
    return await _out(db, conversation)


@router.get("/chat/conversations/{conversation_id}", response_model=ChatConversationOut)
async def get_chat(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatConversationOut:
    try:
        return await _out(db, await service.load_conversation(db, user, conversation_id))
    except service.ChatError as exc:
        raise _raise(exc) from exc


@router.get("/chat/conversations/{conversation_id}/messages", response_model=list[ChatMessageOut])
async def poll_chat(
    conversation_id: uuid.UUID,
    after: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChatMessageOut]:
    try:
        conversation = await service.load_conversation(db, user, conversation_id)
    except service.ChatError as exc:
        raise _raise(exc) from exc
    return [_for_customer(m) for m in await service.messages_after(db, conversation.id, after)]


@router.post("/chat/conversations/{conversation_id}/messages", response_model=ChatConversationOut)
async def send_chat_message(
    conversation_id: uuid.UUID,
    payload: ChatMessageIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatConversationOut:
    try:
        conversation = await service.load_conversation(db, user, conversation_id)
        await service.post_customer_message(
            db, conversation, payload.text, service.intake_provider()
        )
    except service.ChatError as exc:
        raise _raise(exc) from exc
    return await _out(db, conversation)


@router.post("/chat/conversations/{conversation_id}/order", response_model=ChatConversationOut)
async def choose_chat_order(
    conversation_id: uuid.UUID,
    payload: ChatOrderIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatConversationOut:
    try:
        conversation = await service.load_conversation(db, user, conversation_id)
        await service.select_order(db, conversation, payload.order_ref)
    except service.ChatError as exc:
        raise _raise(exc) from exc
    return await _out(db, conversation)


@router.post("/chat/conversations/{conversation_id}/confirm", response_model=ChatConversationOut)
async def confirm_chat(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatConversationOut:
    try:
        conversation = await service.load_conversation(db, user, conversation_id)
        await service.confirm(db, conversation, user)
        conversation = await service.load_conversation(db, user, conversation_id)
    except service.ChatError as exc:
        raise _raise(exc) from exc
    return await _out(db, conversation)


@router.get("/complaints/{ref}/chat", response_model=list[ChatMessageOut])
async def complaint_chat(
    ref: str, _: User = Depends(require_roles(*STAFF_ROLES)), db: AsyncSession = Depends(get_db)
) -> list[ChatMessageOut]:
    conversation = await db.scalar(
        select(ChatConversation)
        .join(Complaint, Complaint.id == ChatConversation.complaint_id)
        .where(Complaint.complaint_ref == ref.upper())
    )
    if conversation is None:
        return []
    return [
        ChatMessageOut.model_validate(m) for m in await service.messages_after(db, conversation.id)
    ]
