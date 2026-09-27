# VoltHaven Storefront Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the demo shop into a premium, complete e-commerce site (all standard pages, motion, search/filters/sort, Contact us feeding complaints or an enquiries inbox, policy pages driven by one config that provably matches the knowledge base).

**Architecture:** Backend first: a shared `config/storefront.yaml` served by `GET /storefront/config` (also the source of checkout delivery days), richer `GET /products` (search, price range, sort incl. real best sellers), `POST /contact` (complaint via `submit_complaint` or an `Enquiry`), staff enquiry endpoints and `POST /newsletter`. Frontend: motion primitives (`motion` library, reduced-motion aware), a new header/footer shell, then the pages, all reading shop facts from the config endpoint.

**Tech Stack:** FastAPI, SQLAlchemy 2.1, Alembic, pytest; Next.js 16, React 19, TanStack Query, shadcn/ui, Tailwind 4, `motion` (new dependency), next-themes.

**Spec:** `docs/superpowers/specs/2026-09-27-storefront-redesign-design.md`

## Global Constraints

- Every number shown on policy pages comes from `config/storefront.yaml`; a test proves each appears in its knowledge-base document.
- Delivery times follow DEL-POL-04: **standard 5 business days, express 2 business days** (the shop currently uses 3/1 — corrected in Task 1; see Ruling below).
- Complaint-topic contact messages go through `complaint_processing.service.submit_complaint` with `channel="web_form"` and require sign-in.
- Enquiry messages are sanitised and redacted (`complaint_processing.preprocessing.sanitize_text`, `complaint_processing.sensitive.redact`).
- Staff endpoints: agent and above (`STAFF_ROLES`); customers 403.
- All motion respects `prefers-reduced-motion` (`MotionConfig reducedMotion="user"`).
- Light theme is the default; dark via toggle.
- No invented reviews/ratings; newsletter UI says nothing is sent (demo).
- Commit only when the user asks (project rule).

**Ruling (planning):** the approved design said "standard 3 business days, express 1"; DEL-POL-04 says 5 and 2. The spec's binding requirement is that site numbers match the knowledge base, so the plan uses 5/2 and updates checkout, product page text and docs. Cost if wrong: two numbers in config.

**Ruling (planning):** spec §5 says a foreign order on the contact form → 404; the existing complaint intake (which contact reuses) answers 422 for unknown or foreign orders (`test_unknown_or_foreign_order_is_rejected`). The plan keeps 422 so both entry points behave the same and don't reveal whether an order reference exists.

**Ruling (planning):** spec §3 lists an "in stock" filter, but products have no stock field (every active product is purchasable). The filter is left out rather than showing a checkbox that changes nothing.

## Review Focus

- A search term with regex/SQL metacharacters (`%`, `_`, `'`, `(`) → treated as literal text, no error (test in Task 2).
- `min_price` greater than `max_price` → empty list, not an error (test in Task 2).
- Contact form submitted twice quickly (double click) with an order problem → the second is rejected as an exact duplicate by the normal intake (409) rather than creating two complaints (test in Task 3).
- Contact message containing a card number → stored redacted in the enquiry (test in Task 3).
- `GET /storefront/config` when a policy value is edited in YAML but not in the documents → the consistency test fails (test in Task 1).

## File Structure

Backend: `config/storefront.yaml` (new), `storefront/config.py` (new: load + typed model), `storefront/orders.py` (delivery days from config), `storefront/queries.py` (new: product search/sort), `support_contact/__init__.py`, `support_contact/service.py` (new: contact routing, enquiries, newsletter), `database/models/contact.py` (new: `Enquiry`, `NewsletterSubscriber`, `ENQUIRY_REF_SEQ`), migration `*_contact_and_newsletter.py`, `src/api/routes/storefront.py` (config endpoint, products params), `src/api/routes/contact.py` (new), `src/api/schemas.py`, `src/main.py`. Tests: `tests/unit/test_storefront_config.py`, `tests/integration/test_catalogue_queries.py`, `tests/integration/test_contact.py`.

Frontend: `web/src/lib/storefront.ts` (config hook, delivery-date helper), `web/src/components/motion/{reveal,stagger,count-up}.tsx`, `web/src/components/shop/{site-header,mega-menu,search-box,mini-cart,site-footer,newsletter-form,theme-toggle,product-carousel,filter-panel,fly-to-cart}.tsx`, pages under `web/src/app/(shop)/…` (home, shop, product, cart, checkout, orders, about, contact, help, shipping, returns, warranty, privacy, terms, about-supportnova, not-found), `web/src/app/(app)/enquiries/page.tsx`, `web/src/components/enquiries/enquiries-inbox.tsx`, sidebar.

---

### Task 1: Shared storefront config

**Files:** Create `config/storefront.yaml`, `storefront/config.py`, `tests/unit/test_storefront_config.py`; Modify `storefront/orders.py` (SHIPPING_DAYS), `src/api/routes/storefront.py`, `src/api/schemas.py`, `tests/unit/test_storefront_orders.py` (expected dates for 5/2 days).

**Interfaces:** Produces `storefront.config.storefront_config() -> StorefrontConfig` (pydantic, `lru_cache`), `StorefrontConfig.shipping.standard_days/express_days/late_credit_pct/late_credit_cap_usd/late_threshold_days`, `.returns.window_days/refund_min_days/refund_max_days/store_credit_days`, `.warranty.months/extended_months`, `.company.*`, `.faq: list[{question, answer}]`; endpoint `GET /storefront/config` → `StorefrontConfig` JSON (operation id `get_storefront_config`).

- [ ] **Step 1: Config data** `config/storefront.yaml`

```yaml
# Shop facts shown on the website. Policy numbers MUST match the knowledge-base documents
# (tests/unit/test_storefront_config.py checks them).
company:
  name: VoltHaven Electronics
  tagline: Electronics that just work, and support that listens.
  address: "Unit 12, Riverside Tech Park, 88 Canal Road, Lahore 54000, Pakistan (fictional)"
  phone: "+92 42 3000 0000"
  support_email: support@volthaven.example
  hours: "Mon–Sat, 9:00–18:00 PKT · AI assistant 24/7"
  socials:
    - {name: Instagram, url: "https://instagram.com/"}
    - {name: X, url: "https://x.com/"}
    - {name: YouTube, url: "https://youtube.com/"}
shipping:           # DEL-POL-04
  standard_days: 5
  express_days: 2
  late_threshold_days: 5
  late_credit_pct: 10
  late_credit_cap_usd: 50
  lost_after_days: 7
returns:            # REF-POL-01
  window_days: 30
  refund_min_days: 7
  refund_max_days: 10
  store_credit_days: 1
warranty:           # WAR-POL-02
  months: 12
  extended_months: 24
faq:
  - question: How long does delivery take?
    answer: "Standard delivery arrives within {standard_days} business days of dispatch and express within {express_days}."
  - question: What if my order is late?
    answer: "If a standard order arrives more than {late_threshold_days} business days late you can receive store credit of {late_credit_pct}% of the order value, up to USD {late_credit_cap_usd}. Late express orders get the express fee back."
  - question: Can I return something I don't want?
    answer: "Unused items in original packaging can be returned within {window_days} days of delivery for a refund of the item price."
  - question: When will I get my refund?
    answer: "Approved refunds reach your original payment method within {refund_min_days} to {refund_max_days} business days of us receiving the item."
  - question: What does the warranty cover?
    answer: "Every product has a {months}-month limited warranty from delivery; VoltCare+ extends it to {extended_months} months."
  - question: How do I report a problem?
    answer: "Use Get help on your order or the chat on any page; our assistant files it for the right team straight away."
```

- [ ] **Step 2: Failing tests** `tests/unit/test_storefront_config.py`

```python
"""Shop facts match the knowledge-base policy documents, word for word where it matters."""

from pathlib import Path

import pytest

from src.core.config import ROOT_DIR
from storefront.config import storefront_config

SOURCES = ROOT_DIR / "sample_documents" / "sources"


def doc(code: str) -> str:
    [path] = list(SOURCES.glob(f"{code}_*.md"))
    return Path(path).read_text()


def test_delivery_numbers_match_the_delivery_policy() -> None:
    s = storefront_config().shipping
    text = doc("DEL-POL-04")
    assert f"Standard delivery arrives within {s.standard_days} business days" in text
    assert f"Express delivery arrives within {s.express_days} business days" in text
    assert f"more than {s.late_threshold_days} business days after the committed" in text
    assert (
        f"store credit of {s.late_credit_pct}% of the order value, up to a maximum of USD {s.late_credit_cap_usd}"
        in text
    )
    assert f"{s.lost_after_days} consecutive business days is treated as lost" in text


def test_return_and_refund_numbers_match_the_refund_policy() -> None:
    r = storefront_config().returns
    text = doc("REF-POL-01")
    assert f"returned within {r.window_days} days of delivery" in text
    assert f"within {r.refund_min_days} to {r.refund_max_days} business days" in text
    assert f"Store-credit refunds are issued within {r.store_credit_days} business day" in text


def test_warranty_numbers_match_the_warranty_policy() -> None:
    w = storefront_config().warranty
    text = doc("WAR-POL-02")
    assert f"{w.months}-month limited warranty" in text
    assert f"extended warranty of {w.extended_months} months" in text


def test_faq_placeholders_are_filled() -> None:
    for item in storefront_config().faq:
        assert "{" not in item.answer, item.question


def test_checkout_uses_the_configured_delivery_days() -> None:
    from storefront.orders import SHIPPING_DAYS

    s = storefront_config().shipping
    assert SHIPPING_DAYS == {"standard": s.standard_days, "express": s.express_days}


@pytest.mark.parametrize("line", ["returns", "warranty"])
def test_sections_exist(line: str) -> None:
    assert getattr(storefront_config(), line) is not None
```

Run: `uv run pytest tests/unit/test_storefront_config.py -q` → FAIL (`No module named 'storefront.config'`).

- [ ] **Step 3: Implement** `storefront/config.py`

```python
"""Shop facts (company details, delivery, returns, warranty, FAQ) from config/storefront.yaml.

Served to the website by `GET /storefront/config`; checkout reads its delivery days from here.
"""

from functools import lru_cache
from typing import Any

import yaml
from pydantic import BaseModel

from src.core.config import ROOT_DIR


class Social(BaseModel):
    name: str
    url: str


class Company(BaseModel):
    name: str
    tagline: str
    address: str
    phone: str
    support_email: str
    hours: str
    socials: list[Social]


class Shipping(BaseModel):
    standard_days: int
    express_days: int
    late_threshold_days: int
    late_credit_pct: int
    late_credit_cap_usd: int
    lost_after_days: int


class Returns(BaseModel):
    window_days: int
    refund_min_days: int
    refund_max_days: int
    store_credit_days: int


class Warranty(BaseModel):
    months: int
    extended_months: int


class FaqItem(BaseModel):
    question: str
    answer: str


class StorefrontConfig(BaseModel):
    company: Company
    shipping: Shipping
    returns: Returns
    warranty: Warranty
    faq: list[FaqItem]


@lru_cache
def storefront_config() -> StorefrontConfig:
    with (ROOT_DIR / "config" / "storefront.yaml").open(encoding="utf-8") as handle:
        raw: dict[str, Any] = yaml.safe_load(handle)
    values = {**raw["shipping"], **raw["returns"], **raw["warranty"]}
    raw["faq"] = [{**f, "answer": f["answer"].format(**values)} for f in raw["faq"]]
    return StorefrontConfig.model_validate(raw)
```

`storefront/orders.py`: replace `SHIPPING_DAYS = {"standard": 3, "express": 1}` with

```python
def _shipping_days() -> dict[str, int]:
    from storefront.config import storefront_config

    s = storefront_config().shipping
    return {"standard": s.standard_days, "express": s.express_days}


SHIPPING_DAYS = _shipping_days()
```

Update `tests/unit/test_storefront_orders.py` expected dates for 5/2 days: `delivery_due(FRIDAY, "standard") == date(2026, 10, 2)`, `delivery_due(FRIDAY, "express") == date(2026, 9, 29)`.

Endpoint in `src/api/routes/storefront.py`:

```python
@router.get("/storefront/config", response_model=StorefrontConfig)
async def get_storefront_config() -> StorefrontConfig:
    return storefront_config()
```

(import `StorefrontConfig, storefront_config` from `storefront.config`.)

- [ ] **Step 4: Run** `uv run pytest -q` → all pass (fix any other test expecting 3/1 days).

---

### Task 2: Catalogue search, price filter and sorting

**Files:** Create `storefront/queries.py`, `tests/integration/test_catalogue_queries.py`; Modify `src/api/routes/storefront.py` (`list_products`).

**Interfaces:** Produces `storefront.queries.product_query(product_line: str | None, q: str | None, min_price: float | None, max_price: float | None, sort: Literal["featured","price_asc","price_desc","newest","best_selling"], today: date) -> Select[tuple[Product]]`; endpoint params `product_line, q, min_price, max_price, sort` on `GET /products`.

- [ ] **Step 1: Failing tests** `tests/integration/test_catalogue_queries.py`

```python
"""Catalogue search, price range and sorting, including real best sellers."""

from collections.abc import Callable
from datetime import date, timedelta

import httpx
import pytest
from sqlalchemy import select

from database.models import Order, Role
from database.session import sync_session

pytestmark = pytest.mark.db


async def skus(client: httpx.AsyncClient, **params: object) -> list[str]:
    response = await client.get("/api/v1/products", params=params)
    assert response.status_code == 200, response.text
    return [p["sku"] for p in response.json()]


async def test_search_matches_name_description_and_specs(client: httpx.AsyncClient) -> None:
    assert set(await skus(client, q="aerobook")) == {"VH-LAP-AB14", "VH-LAP-AB16P"}  # name
    assert "VH-ACC-PB20" in await skus(client, q="20,000 mAh")  # a spec
    assert await skus(client, q="noise-cancelling") == ["VH-AUD-PBP"]  # description


@pytest.mark.parametrize("term", ["%", "_", "'", "(", "\\"])
async def test_search_metacharacters_are_literal(client: httpx.AsyncClient, term: str) -> None:
    assert (await client.get("/api/v1/products", params={"q": term})).status_code == 200


async def test_price_range(client: httpx.AsyncClient) -> None:
    cheap = await skus(client, max_price=40)
    assert set(cheap) == {"VH-ACC-VC65", "VH-ACC-USBC2"}
    assert await skus(client, min_price=500, max_price=100) == []


async def test_price_sorting(client: httpx.AsyncClient) -> None:
    prices = [
        p["price"]
        for p in (await client.get("/api/v1/products", params={"sort": "price_asc"})).json()
    ]
    assert prices == sorted(prices)
    prices = [
        p["price"]
        for p in (await client.get("/api/v1/products", params={"sort": "price_desc"})).json()
    ]
    assert prices == sorted(prices, reverse=True)


async def test_best_sellers_count_recent_non_lost_orders(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    buyer = auth_headers(Role.CUSTOMER)
    for sku, qty in [("VH-AUD-PBP", 1), ("VH-AUD-PBP", 1), ("VH-WEA-ST3", 1)]:
        await client.post(
            "/api/v1/checkout", headers=buyer, json={"lines": [{"sku": sku, "quantity": qty}]}
        )
    for sku in ["VH-ACC-VC65"] * 3:  # three orders, but lost or too old: ignored
        await client.post(
            "/api/v1/checkout", headers=buyer, json={"lines": [{"sku": sku, "quantity": 1}]}
        )
    with sync_session() as db:
        chargers = db.scalars(select(Order).where(Order.product_name.like("VoltCharge 65W%"))).all()
        chargers[0].status = "lost"
        for old in chargers[1:]:
            old.order_date = date.today() - timedelta(days=120)
        db.commit()
    top = await skus(client, sort="best_selling")
    assert top[:2] == ["VH-AUD-PBP", "VH-WEA-ST3"]


async def test_newest_first(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    await client.post(
        "/api/v1/admin/products",
        headers=auth_headers(Role.ADMIN),
        json={
            "sku": "VH-NEW-001",
            "name": "Brand New Thing",
            "product_line": "ACCESSORY",
            "price": 10,
            "description": "Newest product.",
            "specs": [],
        },
    )
    assert (await skus(client, sort="newest"))[0] == "VH-NEW-001"
```

Run → FAIL (unknown params ignored; assertions fail).

- [ ] **Step 2: Implement** `storefront/queries.py`

```python
"""Catalogue queries for the shop: search, price range, sorting (incl. real best sellers)."""

from datetime import date, timedelta
from typing import Literal

from sqlalchemy import Select, String, cast, func, or_, select

from database.models import Order, Product

Sort = Literal["featured", "price_asc", "price_desc", "newest", "best_selling"]
BEST_SELLER_DAYS = 90


def _like(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def product_query(
    product_line: str | None,
    q: str | None,
    min_price: float | None,
    max_price: float | None,
    sort: Sort,
    today: date,
) -> Select[tuple[Product]]:
    stmt = select(Product).where(Product.is_active)
    if product_line:
        stmt = stmt.where(Product.product_line == product_line)
    if q and q.strip():
        pattern = _like(q.strip())
        stmt = stmt.where(
            or_(
                Product.name.ilike(pattern, escape="\\"),
                Product.description.ilike(pattern, escape="\\"),
                cast(Product.specs, String).ilike(pattern, escape="\\"),
            )
        )
    if min_price is not None:
        stmt = stmt.where(Product.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.price <= max_price)
    if sort == "price_asc":
        return stmt.order_by(Product.price, Product.name)
    if sort == "price_desc":
        return stmt.order_by(Product.price.desc(), Product.name)
    if sort == "newest":
        return stmt.order_by(Product.created_at.desc(), Product.name)
    if sort == "best_selling":
        sold = (
            select(Order.product_id, func.sum(Order.quantity).label("sold"))
            .where(
                Order.status != "lost", Order.order_date >= today - timedelta(days=BEST_SELLER_DAYS)
            )
            .group_by(Order.product_id)
            .subquery()
        )
        return stmt.outerjoin(sold, sold.c.product_id == Product.id).order_by(
            func.coalesce(sold.c.sold, 0).desc(), Product.name
        )
    return stmt.order_by(Product.product_line, Product.price)
```

`list_products` in routes: add params `q: str | None = Query(None, max_length=100)`, `min_price: float | None = Query(None, ge=0)`, `max_price: float | None = Query(None, ge=0)`, `sort: Sort = "featured"`; body `return list((await db.scalars(product_query(product_line, q, min_price, max_price, sort, date.today()))).all())`.

- [ ] **Step 3: Run** the new tests and the full suite → pass.

---

### Task 3: Contact us, enquiries and newsletter (backend)

**Files:** Create `database/models/contact.py`, migration `*_contact_and_newsletter.py`, `support_contact/__init__.py`, `support_contact/service.py`, `src/api/routes/contact.py`, `tests/integration/test_contact.py`; Modify `database/models/__init__.py`, `src/api/schemas.py`, `src/main.py`, `security/dependencies.py` (optional-user dependency).

**Interfaces:** Produces model `Enquiry(ref, name, email, topic, message, user_id, customer_id, status, handled_by_id, handled_at, complaint_id, created_at)`, `EnquiryStatus` (`new`, `handled`), `NewsletterSubscriber(email, source, created_at)`, `ENQUIRY_REF_SEQ`; `security.dependencies.get_optional_user` (returns `User | None`, never raises for a missing token, 401 for an invalid one); endpoints `POST /contact` (`ContactIn` → `ContactOut{kind: "complaint"|"enquiry"|"ignored", reference: str | None}`), `GET /enquiries` (`status`, `topic` filters) → `list[EnquiryOut]`, `PATCH /enquiries/{ref}` (`EnquiryUpdate{status}`) → `EnquiryOut`, `POST /enquiries/{ref}/convert` → `EnquiryOut` (with `complaint_ref`), `POST /newsletter` (`NewsletterIn{email, source}`) → 204.

- [ ] **Step 1: Failing tests** `tests/integration/test_contact.py`

```python
"""Contact us routing, the enquiries inbox and newsletter sign-ups."""

from collections.abc import Callable

import httpx
import pytest
from sqlalchemy import func, select

from database.models import Complaint, Enquiry, NewsletterSubscriber, Role, User
from database.session import sync_session

pytestmark = pytest.mark.db

CARD = "4111 1111 1111 1111"


def form(**overrides: object) -> dict[str, object]:
    return {
        "name": "Sara Khan",
        "email": "sara@example.test",
        "topic": "product_question",
        "message": "Does the AeroBook 14 support two external monitors at once?",
        **overrides,
    }


@pytest.fixture
def signed_in(create_user: Callable[..., User], make_token: Callable[..., str]) -> dict[str, str]:
    user = create_user(Role.CUSTOMER, email="sara@example.test")
    return {"Authorization": f"Bearer {make_token(user.clerk_user_id)}"}


async def test_questions_become_enquiries_and_are_redacted(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/contact", json=form(message=f"My card {CARD} was declined, why?")
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["kind"] == "enquiry" and body["reference"].startswith("ENQ-")
    with sync_session() as db:
        enquiry = db.scalar(select(Enquiry))
        assert enquiry is not None and CARD not in enquiry.message
        assert "[card ending 1111]" in enquiry.message


async def test_order_problems_need_sign_in(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/v1/contact", json=form(topic="order_problem"))
    assert response.status_code == 401
    assert "sign in" in response.json()["detail"].lower()


async def test_order_problems_become_web_form_complaints(
    client: httpx.AsyncClient, signed_in: dict[str, str]
) -> None:
    [order] = (
        await client.post(
            "/api/v1/checkout",
            headers=signed_in,
            json={"lines": [{"sku": "VH-TAB-T11", "quantity": 1}]},
        )
    ).json()
    body = form(
        topic="order_problem",
        order_ref=order["order_ref"],
        message="My tablet arrived with a cracked screen and the box was crushed.",
    )
    response = await client.post("/api/v1/contact", json=body, headers=signed_in)
    assert response.status_code == 201, response.text
    assert response.json()["kind"] == "complaint"
    with sync_session() as db:
        complaint = db.scalar(select(Complaint))
        assert complaint is not None and complaint.channel == "web_form"
        assert complaint.order is not None and complaint.order.order_ref == order["order_ref"]
    assert len(client.app.state.analyses) == 1  # type: ignore[attr-defined]
    again = await client.post("/api/v1/contact", json=body, headers=signed_in)
    assert again.status_code == 409  # double submit → the normal duplicate check


async def test_someone_elses_order_is_rejected(
    client: httpx.AsyncClient,
    signed_in: dict[str, str],
    auth_headers: Callable[[Role], dict[str, str]],
) -> None:
    other = auth_headers(Role.CUSTOMER)
    [order] = (
        await client.post(
            "/api/v1/checkout",
            headers=other,
            json={"lines": [{"sku": "VH-TAB-T11", "quantity": 1}]},
        )
    ).json()
    response = await client.post(
        "/api/v1/contact",
        headers=signed_in,
        json=form(
            topic="order_problem",
            order_ref=order["order_ref"],
            message="This order arrived broken and I would like a replacement please.",
        ),
    )
    assert response.status_code == 422


async def test_honeypot_is_ignored_silently(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/v1/contact", json=form(website="http://spam.example"))
    assert response.status_code == 201 and response.json()["kind"] == "ignored"
    with sync_session() as db:
        assert db.scalar(select(func.count()).select_from(Enquiry)) == 0


async def test_enquiry_inbox_is_for_staff(
    client: httpx.AsyncClient,
    signed_in: dict[str, str],
    auth_headers: Callable[[Role], dict[str, str]],
) -> None:
    ref = (await client.post("/api/v1/contact", json=form(), headers=signed_in)).json()["reference"]
    assert (await client.get("/api/v1/enquiries", headers=signed_in)).status_code == 403
    agent = auth_headers(Role.AGENT)
    listed = (await client.get("/api/v1/enquiries", headers=agent, params={"status": "new"})).json()
    assert [e["ref"] for e in listed] == [ref]
    handled = await client.patch(
        f"/api/v1/enquiries/{ref}", headers=agent, json={"status": "handled"}
    )
    assert handled.json()["status"] == "handled"
    converted = (await client.post(f"/api/v1/enquiries/{ref}/convert", headers=agent)).json()
    assert converted["complaint_ref"].startswith("CMP-")


async def test_anonymous_enquiries_cannot_be_converted(
    client: httpx.AsyncClient, auth_headers: Callable[[Role], dict[str, str]]
) -> None:
    ref = (await client.post("/api/v1/contact", json=form())).json()["reference"]
    response = await client.post(
        f"/api/v1/enquiries/{ref}/convert", headers=auth_headers(Role.AGENT)
    )
    assert response.status_code == 422


async def test_newsletter_is_idempotent(client: httpx.AsyncClient) -> None:
    for _ in range(2):
        response = await client.post(
            "/api/v1/newsletter", json={"email": "Fan@Example.test", "source": "footer"}
        )
        assert response.status_code == 204
    assert (await client.post("/api/v1/newsletter", json={"email": "nope"})).status_code == 422
    with sync_session() as db:
        assert db.scalar(select(func.count()).select_from(NewsletterSubscriber)) == 1
```

Run → FAIL (imports).

- [ ] **Step 2: Models** `database/models/contact.py`

```python
"""Contact us enquiries (non-complaint messages) and newsletter sign-ups."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Sequence, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

ENQUIRY_REF_SEQ = Sequence("enquiry_ref_seq", metadata=Base.metadata)


class EnquiryStatus(StrEnum):
    NEW = "new"
    HANDLED = "handled"


class Enquiry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "enquiries"

    ref: Mapped[str] = mapped_column(String(20), unique=True)  # ENQ-000001
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320))
    topic: Mapped[str] = mapped_column(String(30), index=True)
    message: Mapped[str] = mapped_column(Text)  # sanitised and redacted
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customers.id"))
    status: Mapped[EnquiryStatus] = mapped_column(String(20), default=EnquiryStatus.NEW, index=True)
    handled_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    complaint_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("complaints.id"))


class NewsletterSubscriber(Base):
    __tablename__ = "newsletter_subscribers"

    email: Mapped[str] = mapped_column(String(320), primary_key=True)  # lower-cased
    source: Mapped[str] = mapped_column(String(40), default="footer")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

Register in `database/models/__init__.py`. Migration: autogenerate "contact and newsletter", add `op.execute("CREATE SEQUENCE IF NOT EXISTS enquiry_ref_seq")` / drop, `server_default` for `status` (`'new'`) and `source` (`'footer'`), apply.

- [ ] **Step 3: Optional user** in `security/dependencies.py`:

```python
async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    verifier: ClerkTokenVerifier = Depends(get_token_verifier),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """The signed-in user, or None for anonymous visitors (public forms)."""
    if credentials is None:
        return None
    return await get_current_user(credentials=credentials, verifier=verifier, db=db)
```

(Match `get_current_user`'s actual parameter names when adding this.)

- [ ] **Step 4: Service** `support_contact/service.py`

```python
"""Contact us: order problems become complaints (normal intake), everything else an enquiry."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from complaint_processing.preprocessing import sanitize_text
from complaint_processing.sensitive import redact
from complaint_processing.service import (
    ComplaintInput,
    get_or_create_customer,
    next_ref,
    submit_complaint,
)
from database import audit
from database.models import (
    ENQUIRY_REF_SEQ,
    Complaint,
    Customer,
    Enquiry,
    EnquiryStatus,
    NewsletterSubscriber,
    User,
)

COMPLAINT_TOPIC = "order_problem"
TOPIC_TITLES = {"order_problem": "Problem with an order"}


class ContactError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def clean(text: str) -> str:
    return redact(sanitize_text(text)).text


async def submit_contact(
    db: AsyncSession,
    user: User | None,
    *,
    name: str,
    email: str,
    topic: str,
    message: str,
    order_ref: str | None,
) -> tuple[str, str]:
    """Returns (kind, reference)."""
    if topic == COMPLAINT_TOPIC:
        if user is None:
            raise ContactError(
                401,
                "Please sign in to report a problem with an order, so we can look at your orders.",
            )
        customer = await get_or_create_customer(db, user)
        first_line = sanitize_text(message).split("\n")[0][:70]
        complaint = await submit_complaint(db, customer=customer, submitted_by=user,
            data=ComplaintInput(title=first_line or TOPIC_TITLES[topic], description=message,
                                order_ref=order_ref, channel="web_form"))  # fmt: skip
        return "complaint", complaint.complaint_ref
    customer = (
        await db.scalar(select(Customer).where(Customer.user_id == user.id)) if user else None
    )
    enquiry = Enquiry(ref=await next_ref(db, "ENQ", ENQUIRY_REF_SEQ), name=clean(name)[:200],
                      email=email.strip().lower(), topic=topic, message=clean(message),
                      user_id=user.id if user else None,
                      customer_id=customer.id if customer else None)  # fmt: skip
    db.add(enquiry)
    await audit.record(
        db,
        "enquiry.received",
        "enquiry",
        enquiry.ref,
        actor_user_id=user.id if user else None,
        after={"topic": topic},
    )
    await db.commit()
    return "enquiry", enquiry.ref


async def mark(db: AsyncSession, enquiry: Enquiry, status: EnquiryStatus, actor: User) -> None:
    enquiry.status = status
    enquiry.handled_by_id = actor.id if status == EnquiryStatus.HANDLED else None
    enquiry.handled_at = datetime.now(UTC) if status == EnquiryStatus.HANDLED else None
    await audit.record(
        db,
        "enquiry.status_changed",
        "enquiry",
        enquiry.ref,
        actor_user_id=actor.id,
        after={"status": status},
    )
    await db.commit()


async def convert(db: AsyncSession, enquiry: Enquiry, actor: User) -> Complaint:
    if enquiry.customer_id is None or enquiry.complaint_id is not None:
        raise ContactError(
            422, "Only enquiries from signed-in customers can be converted, and only once."
        )
    customer = await db.get(Customer, enquiry.customer_id)
    assert customer is not None
    ref = enquiry.ref
    complaint = await submit_complaint(db, customer=customer, submitted_by=actor,
        data=ComplaintInput(title=f"From enquiry {ref}", description=enquiry.message,
                            channel="web_form"))  # fmt: skip
    enquiry = await db.scalar(select(Enquiry).where(Enquiry.ref == ref))
    assert enquiry is not None
    enquiry.complaint_id = complaint.id
    enquiry.status = EnquiryStatus.HANDLED
    enquiry.handled_by_id, enquiry.handled_at = actor.id, datetime.now(UTC)
    await audit.record(
        db,
        "enquiry.converted",
        "enquiry",
        ref,
        actor_user_id=actor.id,
        after={"complaint": complaint.complaint_ref},
    )
    await db.commit()
    return complaint


async def subscribe(db: AsyncSession, email: str, source: str) -> None:
    await db.execute(
        insert(NewsletterSubscriber)
        .values(email=email.strip().lower(), source=source)
        .on_conflict_do_nothing(index_elements=["email"])
    )
    await db.commit()
```

- [ ] **Step 5: Schemas and routes** — `ContactIn{name: str(1..200), email: EmailStr-like pattern, topic: Literal[order_problem, product_question, business, feedback, other], message: str(10..5000), order_ref: str | None, website: str | None}`, `ContactOut{kind, reference}`, `EnquiryOut{ref, name, email, topic, message, status, created_at, handled_at, complaint_ref}`, `EnquiryUpdate{status: Literal["new","handled"]}`, `NewsletterIn{email (pattern), source: str = "footer"}`. `src/api/routes/contact.py`:

```python
@router.post("/contact", response_model=ContactOut, status_code=201)
async def contact(
    payload: ContactIn,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> ContactOut:
    if payload.website:  # honeypot: humans never fill the hidden field
        return ContactOut(kind="ignored", reference=None)
    try:
        kind, ref = await submit_contact(
            db,
            user,
            name=payload.name,
            email=payload.email,
            topic=payload.topic,
            message=payload.message,
            order_ref=payload.order_ref,
        )
    except ContactError as exc:
        raise HTTPException(exc.status, exc.message) from exc
    except ComplaintValidationError as exc:
        raise HTTPException(422, "; ".join(exc.issues)) from exc
    except DuplicateComplaintError as exc:
        raise HTTPException(409, str(exc)) from exc
    return ContactOut(kind=kind, reference=ref)
```

plus `GET /enquiries`, `PATCH /enquiries/{ref}`, `POST /enquiries/{ref}/convert` (staff via `require_roles(*STAFF_ROLES)`; 404 for unknown ref; `complaint_ref` resolved through `complaint_id`), `POST /newsletter` → 204. Register router in `src/main.py`.

- [ ] **Step 6: Run** `uv run pytest tests/integration/test_contact.py -q` and the full suite → pass; ruff + mypy clean; `make openapi`.

---

### Task 4: Design foundation (motion, config hook, header, footer, mini-cart)

**Files:** `pnpm --dir web add motion`; Create `web/src/lib/storefront.ts`, `web/src/components/motion/{reveal,stagger,count-up}.tsx`, `web/src/components/shop/{site-header,mega-menu,search-box,mini-cart,site-footer,newsletter-form,theme-toggle}.tsx`; Modify `web/src/app/(shop)/layout.tsx`, `web/src/components/providers.tsx` (`defaultTheme="light"`, `MotionConfig reducedMotion="user"`), `web/src/app/globals.css` (accent token `--brand` light/dark), remove `shop-header.tsx`.

**Interfaces:** `useStorefront()` → `UseQueryResult<StorefrontConfig>` (staleTime Infinity); `deliveryBy(method: "standard"|"express", from?: Date) → Date` (adds business days from config); `<Reveal delay?>`, `<Stagger>` + `<StaggerItem>`, `<CountUp to suffix?>`; `<MiniCart />` opened by `window.dispatchEvent(new Event("volthaven:open-cart"))`; `<NewsletterForm source />`.

Key code — `web/src/components/motion/reveal.tsx`:

```tsx
"use client";

import { motion } from "motion/react";

/** Fades and rises into view once, when scrolled to (off under reduced motion). */
export function Reveal({ children, delay = 0, className }: {
  children: React.ReactNode; delay?: number; className?: string;
}) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1], delay }}
    >
      {children}
    </motion.div>
  );
}
```

`stagger.tsx` — `Stagger` = `motion.div` with `variants={{ show: { transition: { staggerChildren: 0.08 } } }}`, `initial="hidden" whileInView="show" viewport={{ once: true }}`; `StaggerItem` = `motion.div` with `variants={{ hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }}`.

`count-up.tsx` — `useMotionValue(0)`, `animate(value, to, { duration: 1.2 })` started by `useInView`, rendered through `useTransform(v => Math.round(v))`.

Header behaviour: `useScroll` → `scrolled` when `scrollY > 8` (transparent → `bg-background/80 backdrop-blur border-b`); Shop mega-menu (`DropdownMenu` wide panel with category tiles using the first product image per line from `listProductsOptions`); Support menu; `SearchBox` (debounced 200 ms, top 5 matches via `listProductsOptions({query:{q}})`, Enter → `/shop?q=`); cart button with `motion.span` badge keyed by count (pop on change) opening `MiniCart` (`Sheet` right: lines, subtotal, Checkout/View cart); account (`UserButton`/`SignInButton`, staff console link); mobile `Sheet` menu.

Footer: four columns (Shop: categories; Support: Help centre, Track order, Contact, Shipping, Returns, Warranty; Company: About, How our support works (`/about-supportnova`); Legal: Privacy, Terms), `NewsletterForm` (calls `subscribe`, toast "Subscribed — this demo never sends e-mails"), socials from config, `ThemeToggle` (`useTheme`), fictional-company note.

- [ ] Verify: lint, typecheck, build; browser: header states, mega-menu, search suggestions, mini-cart, footer, theme toggle, reduced motion (emulate with `window.matchMedia` check in devtools or the OS setting).

---

### Task 5: Home page

**Files:** `web/src/app/(shop)/page.tsx`, `web/src/components/shop/{hero,product-carousel,feature-spotlight,why-volthaven,support-callout}.tsx`.

Sections per spec §3 using `listProductsOptions({query:{sort:"newest"}})` and `{sort:"best_selling"}` (first 8 each), spotlight product `VH-LAP-AB14` (specs animate with `CountUp` where numeric), Why VoltHaven numbers from `useStorefront()` (`shipping.express_days`, `warranty.months`, `returns.window_days`, "24/7"), support callout dispatching `volthaven:open-chat`. Hero: headline words wrapped in `motion.span` with staggered `y: "100%" → 0`; product image (`ProductImage`) in `motion.div` with `animate={{ y: [0, -12, 0] }}` (repeat, 6 s) and a blurred accent glow; parallax via `useScroll`/`useTransform` (y 0 → 80 px over the hero).

`ProductCarousel`: horizontal `overflow-x-auto snap-x` row of `ProductCard`s with arrow buttons (`scrollBy`) on desktop, hidden scrollbar.

- [ ] Verify in browser (desktop + 390 px wide), reduced motion.

---

### Task 6: Shop listing and product page

**Files:** `web/src/app/(shop)/shop/page.tsx`, `web/src/components/shop/{filter-panel,fly-to-cart}.tsx`, `web/src/app/(shop)/shop/[sku]/product-detail.tsx`.

Listing: URL-driven state (`line`, `q`, `min`, `max`, `sort` in search params via `useRouter().replace`); `FilterPanel` (category list with counts from an unfiltered `listProductsOptions()`, price range two inputs with presets, clear) as sidebar ≥ lg, `Sheet` below; sort `Select`; results `Stagger` grid with `AnimatePresence` + `layout` on cards; empty state; count "N products".

Product page: gallery (main image with CSS hover zoom `scale-150` following the pointer via `transform-origin`), thumbnails, quantity select, **Add to cart** triggers `FlyToCart` (a `motion.div` dot animating from the button's rect to the header cart icon `#cart-button` rect, then `cart.add`), delivery estimate `Order today, arrives by {weekday, d MMM}` via `deliveryBy("standard")`, `Tabs` Details (description + specs) / Shipping (config text) / Returns (config text), "You may also like" = same product line, excluding itself, else best sellers.

- [ ] Verify filters, sorting, search results, gallery, fly-to-cart, estimate text uses 5 business days.

---

### Task 7: Cart, checkout and orders restyle

**Files:** `web/src/app/(shop)/{cart,checkout,orders}/page.tsx`, `web/src/components/shop/order-list.tsx`.

Cart: two-column with summary card, quantity steppers, remove with `AnimatePresence` exit. Checkout: two-column (shipping choice cards showing "arrives by …" from `deliveryBy`, order summary), and on success an animated confirmation panel (check icon scale-in, checkout reference, links to My orders / Keep shopping) instead of immediate redirect. Orders: cards per purchase with timeline dots (Ordered → Due → Delivered/Lost), existing Get help and admin Demo controls kept.

- [ ] Verify the full purchase flow (signed-in walk-through by the user) and that shipping text says 5/2 business days.

---

### Task 8: Company and help pages, 404

**Files:** `web/src/app/(shop)/{about,help,shipping,returns,warranty,privacy,terms}/page.tsx`, `web/src/app/(shop)/about-supportnova/page.tsx` (moved from current `/about`), `web/src/app/(shop)/not-found.tsx`, `web/src/components/shop/{article-layout,faq-accordion}.tsx`.

`ArticleLayout` (title, lead, sticky table of contents built from `sections: {id, title}[]`, prose content). Pages read `useStorefront()`; every number rendered from config (shipping/express days, late credit % and cap and threshold, lost-after days, return window, refund days, store-credit days, warranty months/extended). Help: search input filtering `faq` + links to policy pages and "Chat with us". Privacy/Terms: plain-language fictional text with the fictional-company notice. 404: friendly message, search box, links to Shop and Help.

- [ ] Verify each page renders and shows config numbers; reduced motion.

---

### Task 9: Contact page and staff Enquiries inbox

**Files:** `web/src/app/(shop)/contact/page.tsx`, `web/src/components/shop/contact-form.tsx`, `web/src/app/(app)/enquiries/page.tsx`, `web/src/components/enquiries/enquiries-inbox.tsx`, `web/src/components/app-sidebar.tsx` (Enquiries, STAFF), `make openapi`.

Contact form: name, email (prefilled for signed-in users), topic select, order select (signed-in + `order_problem`, from `myShopOrdersOptions`), message (10–5000), hidden honeypot `website` input (`tabIndex=-1`, `aria-hidden`, visually hidden). If `order_problem` and signed out: inline notice with SignInButton and "or chat with us". Success panel: complaint → "Complaint {ref} filed — track it in My orders / complaints"; enquiry → "Thanks — we'll reply within 1 business day ({ref})". Side panel: address, phone, e-mail, hours from config, "Chat with us" button.

Inbox: table (ref, received, name/email, topic, first line, status) with status/topic filters, row expands to full message with **Mark handled / Reopen** and **Convert to complaint** (disabled with tooltip when no account); invalidates on success.

- [ ] Verify: enquiry and complaint submissions, sign-in prompt, inbox actions (staff).

---

### Task 10: Docs, full checks, final review

- [ ] `documentation/user_guide.md` (shop pages, contact, enquiries inbox), `README.md`, `documentation/demo_script.md` (home tour, contact complaint), `AI_USAGE.md` entry.
- [ ] `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -q`; `pnpm --dir web lint && pnpm --dir web typecheck && pnpm --dir web build`.
- [ ] Browser walk-through: every page at 1280 px and 390 px, light and dark, reduced motion on.
- [ ] Final whole-branch review (fresh reviewer), fix Critical/Important with RED→GREEN tests.
