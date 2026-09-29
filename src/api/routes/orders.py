"""Order actions, history and receipts for customers, and the staff orders API."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import audit
from database.models import Complaint, Order, User
from database.session import get_db
from security.dependencies import STAFF_ROLES, get_current_user, require_roles
from src.api.schemas import (
    OrderActionIn,
    OrderEventOut,
    ReturnIn,
    ShopOrderOut,
    StaffOrderDetailOut,
    StaffOrderOut,
)
from storefront.lifecycle import LifecycleError
from storefront.order_service import (
    OrderNotFound,
    customer_cancel,
    customer_return,
    list_orders,
    load_order,
    own_order,
    staff_action,
)
from storefront.receipt import build_receipt

router = APIRouter(tags=["orders"])


def _conflict(exc: LifecycleError) -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT, f"{exc} (the order is {exc.stage.replace('_', ' ')})."
    )


async def _visible(db: AsyncSession, user: User, ref: str) -> Order:
    """Staff see any order; a customer only their own (others get 404)."""
    if user.role in STAFF_ROLES:
        order = await load_order(db, ref)
        if order is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
        return order
    try:
        return await own_order(db, user, ref)
    except OrderNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found") from exc


@router.post("/orders/{ref}/cancel", response_model=ShopOrderOut)
async def cancel_order(
    ref: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> Order:
    try:
        return await customer_cancel(db, user, ref)
    except OrderNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found") from exc
    except LifecycleError as exc:
        raise _conflict(exc) from exc


@router.post("/orders/{ref}/return", response_model=ShopOrderOut)
async def request_return(
    ref: str,
    payload: ReturnIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Order:
    try:
        return await customer_return(db, user, ref, payload.reason)
    except OrderNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found") from exc
    except LifecycleError as exc:
        raise _conflict(exc) from exc


@router.get("/orders/{ref}/events", response_model=list[OrderEventOut])
async def order_events(
    ref: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[object]:
    return list((await _visible(db, user, ref)).events)


@router.get(
    "/orders/{ref}/receipt.pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def order_receipt(
    ref: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> Response:
    order = await _visible(db, user, ref)
    return Response(
        build_receipt(order, order.customer),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="receipt-{order.order_ref}.pdf"',
            "Cache-Control": "private, no-store",
        },
    )


# --- staff ---------------------------------------------------------------------------

staff = require_roles(*STAFF_ROLES)


def _staff_out(order: Order) -> StaffOrderOut:
    return StaffOrderOut(
        **ShopOrderOut.model_validate(order).model_dump(),
        customer_name=order.customer.full_name,
        customer_email=order.customer.email,
        manual_hold=order.manual_hold,
    )


@router.get("/admin/orders", response_model=list[StaffOrderOut])
async def staff_orders(
    stage: str | None = None,
    q: str | None = None,
    needs_action: bool = False,
    limit: int = 50,
    offset: int = 0,
    _: User = Depends(staff),
    db: AsyncSession = Depends(get_db),
) -> list[StaffOrderOut]:
    orders = await list_orders(
        db, stage=stage, q=q, needs_action=needs_action, limit=limit, offset=offset
    )
    return [_staff_out(o) for o in orders]


@router.get("/admin/orders/{ref}", response_model=StaffOrderDetailOut)
async def staff_order(
    ref: str, _: User = Depends(staff), db: AsyncSession = Depends(get_db)
) -> StaffOrderDetailOut:
    order = await load_order(db, ref)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    refs = list(
        await db.scalars(select(Complaint.complaint_ref).where(Complaint.order_id == order.id))
    )
    base = _staff_out(order).model_dump()
    return StaffOrderDetailOut(
        **base, events=[OrderEventOut.model_validate(e) for e in order.events], complaint_refs=refs
    )


@router.post("/admin/orders/{ref}/actions", response_model=StaffOrderOut)
async def staff_order_action(
    ref: str,
    payload: OrderActionIn,
    user: User = Depends(staff),
    db: AsyncSession = Depends(get_db),
) -> StaffOrderOut:
    try:
        order = await staff_action(
            db,
            user,
            ref,
            payload.action,
            note=payload.note,
            new_date=payload.new_date,
            days_late=payload.days_late,
        )
    except OrderNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found") from exc
    except LifecycleError as exc:
        raise _conflict(exc) from exc
    await audit.record(
        db,
        "order.stage_changed",
        "order",
        order.order_ref,
        actor_user_id=user.id,
        after={"action": payload.action, "stage": order.stage},
    )
    await db.commit()
    return _staff_out(order)
