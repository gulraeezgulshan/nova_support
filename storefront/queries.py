"""Catalogue queries for the shop: search, price range and sorting (incl. real best sellers)."""

from datetime import date, timedelta
from typing import Literal

from sqlalchemy import Select, func, or_, select

from database.models import Order, Product

Sort = Literal["featured", "price_asc", "price_desc", "newest", "best_selling"]
BEST_SELLER_DAYS = 90


def _contains(term: str) -> str:
    """A LIKE pattern matching `term` literally (%, _ and \\ escaped)."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def product_query(
    *,
    product_line: str | None = None,
    q: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    sort: Sort = "featured",
    today: date,
) -> Select[Product]:
    stmt = select(Product).where(Product.is_active)
    if product_line:
        stmt = stmt.where(Product.product_line == product_line)
    if q and q.strip():
        pattern = _contains(q.strip())
        spec = func.jsonb_array_elements_text(Product.specs).table_valued("value")
        stmt = stmt.where(
            or_(
                Product.name.ilike(pattern, escape="\\"),
                Product.description.ilike(pattern, escape="\\"),
                select(spec.c.value).where(spec.c.value.ilike(pattern, escape="\\")).exists(),
            )
        )
    if min_price is not None:
        stmt = stmt.where(Product.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.price <= max_price)
    match sort:
        case "price_asc":
            return stmt.order_by(Product.price, Product.name)
        case "price_desc":
            return stmt.order_by(Product.price.desc(), Product.name)
        case "newest":
            return stmt.order_by(Product.created_at.desc(), Product.name)
        case "best_selling":
            sold = (
                select(Order.product_id, func.sum(Order.quantity).label("sold"))
                .where(
                    Order.status != "lost",
                    Order.order_date >= today - timedelta(days=BEST_SELLER_DAYS),
                )
                .group_by(Order.product_id)
                .subquery()
            )
            return stmt.outerjoin(sold, sold.c.product_id == Product.id).order_by(
                func.coalesce(sold.c.sold, 0).desc(), Product.name
            )
        case _:
            return stmt.order_by(Product.product_line, Product.price)
