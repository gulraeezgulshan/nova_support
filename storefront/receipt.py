"""A one-page PDF receipt in the currency the customer paid in."""

from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

import app_settings
from database.models import Customer, Order
from storefront.order_emails import format_amount


def build_receipt(order: Order, customer: Customer) -> bytes:
    shop = app_settings.runtime().branding
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle(f"Receipt {order.order_ref}")
    y = A4[1] - 25 * mm
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(20 * mm, y, shop.shop_name)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(20 * mm, y - 6 * mm, f"{shop.address} · {shop.phone} · {shop.support_email}")
    rows = [
        ("Receipt", order.order_ref),
        ("Date", f"{order.order_date:%d %b %Y}"),
        ("Customer", f"{customer.full_name} ({customer.email or 'no e-mail'})"),
        ("Product", f"{order.product_name}, quantity {order.quantity}"),
        ("Shipping", order.shipping_method),
        ("Total", format_amount(order)),
        ("USD reference", f"USD {order.amount:,.2f} at 1 USD = {order.fx_rate:g} {order.currency}"),
        ("Payment", order.transaction_ref or "—"),
        ("Status", order.stage.replace("_", " ")),
    ]
    pdf.setFont("Helvetica", 11)
    y -= 22 * mm
    for label, value in rows:
        pdf.drawString(20 * mm, y, label)
        pdf.drawString(70 * mm, y, value)
        y -= 8 * mm
    pdf.setFont("Helvetica-Oblique", 8)
    pdf.drawString(
        20 * mm,
        15 * mm,
        "VoltHaven Electronics is a fictional company created for a student project.",
    )
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
