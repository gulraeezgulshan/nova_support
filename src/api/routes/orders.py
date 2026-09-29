"""Customer order actions, history and receipts (staff routes are added in Task 9)."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Order, User
from database.session import get_db
from security.dependencies import STAFF_ROLES, get_current_user
from src.api.schemas import OrderEventOut, ReturnIn, ShopOrderOut
from storefront.lifecycle import LifecycleError
from storefront.order_service import (
    OrderNotFound,
    customer_cancel,
    customer_return,
    load_order,
    own_order,
)  # fmt: skip
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
async def cancel_order(ref: str, user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_db)) -> Order:  # fmt: skip
    try:
        return await customer_cancel(db, user, ref)
    except OrderNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found") from exc
    except LifecycleError as exc:
        raise _conflict(exc) from exc


@router.post("/orders/{ref}/return", response_model=ShopOrderOut)
async def request_return(ref: str, payload: ReturnIn, user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_db)) -> Order:  # fmt: skip
    try:
        return await customer_return(db, user, ref, payload.reason)
    except OrderNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found") from exc
    except LifecycleError as exc:
        raise _conflict(exc) from exc


@router.get("/orders/{ref}/events", response_model=list[OrderEventOut])
async def order_events(ref: str, user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_db)) -> list[object]:  # fmt: skip
    return list((await _visible(db, user, ref)).events)


@router.get("/orders/{ref}/receipt.pdf", response_class=Response,
            responses={200: {"content": {"application/pdf": {}}}})  # fmt: skip
async def order_receipt(ref: str, user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_db)) -> Response:  # fmt: skip
    order = await _visible(db, user, ref)
    return Response(
        build_receipt(order, order.customer), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="receipt-{order.order_ref}.pdf"',
                 "Cache-Control": "private, no-store"},
    )  # fmt: skip
