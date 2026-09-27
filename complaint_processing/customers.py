"""Find the customer an e-mail address belongs to, or create one (e-mail and bulk upload)."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from complaint_processing.service import get_or_create_customer, next_ref
from database.models import CUSTOMER_REF_SEQ, Customer, CustomerType, User


async def customer_for_email(db: AsyncSession, email: str, name: str | None) -> Customer:
    address = email.strip().lower()
    customer = await db.scalar(
        select(Customer)
        .where(func.lower(Customer.email) == address)
        .order_by(Customer.created_at)
        .limit(1)
    )
    if customer is not None:
        return customer
    user = await db.scalar(select(User).where(func.lower(User.email) == address))
    if user is not None:
        return await get_or_create_customer(db, user)
    customer = Customer(
        customer_ref=await next_ref(db, "CUST", CUSTOMER_REF_SEQ),
        full_name=(name or address.split("@")[0])[:200],
        email=address,
        customer_type=CustomerType.STANDARD,
    )
    db.add(customer)
    await db.flush()
    return customer
