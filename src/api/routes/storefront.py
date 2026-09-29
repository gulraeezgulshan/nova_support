"""Demo shop: public catalogue, customer checkout and orders, admin delivery outcomes."""

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import app_settings
from complaint_processing.service import get_or_create_customer
from database import audit
from database.models import Customer, FxRate, Order, Product, ProductImage, Role, User
from database.session import get_db
from security.dependencies import get_current_user, require_roles
from src.api.schemas import (
    CheckoutIn,
    CurrencyInfo,
    CurrencyOut,
    ImageOrderIn,
    ProductCreate,
    ProductImageOut,
    ProductOut,
    ProductUpdate,
    ShopOrderOut,
)
from src.core.storage import Storage, get_storage
from storefront.catalogue import PRODUCT_LINES
from storefront.config import StorefrontConfig, storefront_config
from storefront.currency import CURRENCIES, current_rates_async
from storefront.images import ImageError, add_image, remove, reorder
from storefront.orders import CheckoutError, CheckoutLine, checkout
from storefront.queries import Sort, product_query

router = APIRouter(tags=["storefront"])


async def _with_images(db: AsyncSession, orders: list[Order]) -> list[ShopOrderOut]:
    """Orders with their product's main image (shop orders only; dataset orders have none)."""
    product_ids = {o.product_id for o in orders if o.product_id}
    main = (
        {
            image.product_id: ProductImageOut.model_validate(image).url
            for image in await db.scalars(
                select(ProductImage).where(
                    ProductImage.product_id.in_(product_ids), ProductImage.position == 0
                )
            )
        }
        if product_ids
        else {}
    )
    return [
        ShopOrderOut.model_validate(o).model_copy(
            update={"image_url": main.get(o.product_id) if o.product_id else None}
        )
        for o in orders
    ]


@router.get("/storefront/config", response_model=StorefrontConfig)
async def get_storefront_config() -> StorefrontConfig:
    """Company details (from Settings), delivery, returns and warranty facts, and the FAQ."""
    config = storefront_config()
    b = app_settings.runtime().branding
    company = config.company.model_copy(
        update={"name": b.shop_name, "tagline": b.shop_tagline, "address": b.address,
                "phone": b.phone, "support_email": b.support_email, "hours": b.hours}
    )  # fmt: skip
    return config.model_copy(update={"company": company})


@router.get("/currency", response_model=CurrencyOut)
async def currency_rates(db: AsyncSession = Depends(get_db)) -> CurrencyOut:
    rates = await current_rates_async(db)
    fetched = await db.scalar(select(func.max(FxRate.fetched_at)))
    return CurrencyOut(
        rates={c: float(r) for c, r in rates.items()},
        fetched_at=fetched,
        currencies=[
            CurrencyInfo(code=c.code, symbol=c.symbol, decimals=c.decimals)
            for c in CURRENCIES.values()
        ],
    )


@router.get("/products", response_model=list[ProductOut])
async def list_products(
    product_line: str | None = Query(None),
    q: str | None = Query(None, max_length=100, description="Search name, description, specs"),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    sort: Sort = Query("featured"),
    db: AsyncSession = Depends(get_db),
) -> list[Product]:
    stmt = product_query(
        product_line=product_line,
        q=q,
        min_price=min_price,
        max_price=max_price,
        sort=sort,
        today=date.today(),
    )
    return list((await db.scalars(stmt)).all())


@router.get("/products/{sku}", response_model=ProductOut)
async def get_product(sku: str, db: AsyncSession = Depends(get_db)) -> Product:
    product = await db.scalar(select(Product).where(Product.sku == sku, Product.is_active))
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return product


@router.post("/checkout", response_model=list[ShopOrderOut], status_code=status.HTTP_201_CREATED)
async def place_order(
    payload: CheckoutIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Order]:
    customer = await get_or_create_customer(db, user)
    try:
        orders = await checkout(
            db,
            customer,
            [CheckoutLine(line.sku, line.quantity) for line in payload.lines],
            payload.shipping_method,
            date.today(),
            currency=payload.currency,
            rates=await current_rates_async(db),
        )
    except CheckoutError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "; ".join(exc.issues)) from exc
    await audit.record(
        db,
        "shop.checkout",
        "customer",
        customer.id,
        actor_user_id=user.id,
        after={"orders": [o.order_ref for o in orders]},
    )
    await db.commit()
    return orders


@router.get("/orders", response_model=list[ShopOrderOut])
async def my_shop_orders(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[ShopOrderOut]:
    customer = await db.scalar(select(Customer).where(Customer.user_id == user.id))
    if customer is None:
        return []
    orders = (
        await db.scalars(
            select(Order)
            .where(Order.customer_id == customer.id)
            .order_by(Order.order_date.desc(), Order.order_ref.desc())
        )
    ).all()
    return await _with_images(db, list(orders))


# --- product images (public) and product administration ---------------------------------

admin_only = require_roles(Role.ADMIN)


@router.get(
    "/product-images/{image_id}",
    response_class=Response,
    responses={200: {"content": {"image/*": {}}}},
)
async def product_image(
    image_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    storage: Storage = Depends(get_storage),
) -> Response:
    image = await db.get(ProductImage, image_id)
    if image is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Image not found")
    # Each upload gets a new id, so the content at this address never changes.
    return Response(
        storage.get(image.storage_key),
        media_type=image.media_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


async def _product(db: AsyncSession, sku: str) -> Product:
    product = await db.scalar(select(Product).where(Product.sku == sku.upper()))
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return product


def _check_line(line: str | None) -> None:
    if line is not None and line not in PRODUCT_LINES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Unknown product line '{line}' (use one of {', '.join(PRODUCT_LINES)}).",
        )


def _specs(specs: list[str]) -> list[str]:
    return [s.strip()[:120] for s in specs if s.strip()]


@router.get("/admin/products", response_model=list[ProductOut])
async def admin_list_products(
    _: User = Depends(admin_only), db: AsyncSession = Depends(get_db)
) -> list[Product]:
    return list(
        (await db.scalars(select(Product).order_by(Product.product_line, Product.name))).all()
    )


@router.post("/admin/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    actor: User = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
) -> Product:
    _check_line(payload.product_line)
    if await db.scalar(select(Product.id).where(Product.sku == payload.sku)):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Product {payload.sku} already exists")
    product = Product(
        sku=payload.sku,
        name=payload.name.strip(),
        product_line=payload.product_line,
        price=Decimal(str(payload.price)).quantize(Decimal("0.01")),
        description=payload.description.strip(),
        specs=_specs(payload.specs),
        is_active=True,
        images=[],
    )
    db.add(product)
    await db.flush()
    await audit.record(
        db,
        "product.created",
        "product",
        product.sku,
        actor_user_id=actor.id,
        after=payload.model_dump(),
    )
    await db.commit()
    return product


@router.patch("/admin/products/{sku}", response_model=ProductOut)
async def update_product(
    sku: str,
    payload: ProductUpdate,
    actor: User = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
) -> Product:
    product = await _product(db, sku)
    changes = payload.model_dump(exclude_unset=True)
    _check_line(changes.get("product_line"))
    before = {k: str(getattr(product, k)) for k in changes}
    for key, value in changes.items():
        if key == "price":
            value = Decimal(str(value)).quantize(Decimal("0.01"))
        elif key == "specs":
            value = _specs(value)
        elif isinstance(value, str):
            value = value.strip()
        setattr(product, key, value)
    await audit.record(
        db,
        "product.updated",
        "product",
        product.sku,
        actor_user_id=actor.id,
        before=before,
        after={k: str(v) for k, v in changes.items()},
    )
    await db.commit()
    await db.refresh(product)
    return product


@router.post(
    "/admin/products/{sku}/images",
    response_model=ProductImageOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_product_image(
    sku: str,
    file: UploadFile = File(...),
    actor: User = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
    storage: Storage = Depends(get_storage),
) -> ProductImage:
    product = await _product(db, sku)
    data = await file.read()
    try:
        image = await add_image(db, product, data, storage)
    except ImageError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    await audit.record(
        db,
        "product.image_added",
        "product",
        product.sku,
        actor_user_id=actor.id,
        after={"image": str(image.id), "bytes": image.size_bytes},
    )
    await db.commit()
    return image


@router.put("/admin/products/{sku}/images/order", response_model=ProductOut)
async def reorder_product_images(
    sku: str,
    payload: ImageOrderIn,
    actor: User = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
) -> Product:
    product = await _product(db, sku)
    try:
        reorder(product, payload.image_ids)
    except ImageError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    await audit.record(
        db,
        "product.images_reordered",
        "product",
        product.sku,
        actor_user_id=actor.id,
        after={"order": [str(i) for i in payload.image_ids]},
    )
    await db.commit()
    return product


@router.delete("/admin/products/{sku}/images/{image_id}", response_model=ProductOut)
async def delete_product_image(
    sku: str,
    image_id: uuid.UUID,
    actor: User = Depends(admin_only),
    db: AsyncSession = Depends(get_db),
    storage: Storage = Depends(get_storage),
) -> Product:
    product = await _product(db, sku)
    try:
        remove(product, image_id, storage)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Image not found") from exc
    await audit.record(
        db,
        "product.image_removed",
        "product",
        product.sku,
        actor_user_id=actor.id,
        after={"image": str(image_id)},
    )
    await db.commit()
    return product
