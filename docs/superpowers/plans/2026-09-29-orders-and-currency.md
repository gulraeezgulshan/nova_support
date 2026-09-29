# Orders Lifecycle and Local Currency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Shop orders move through a courier-like lifecycle (automatically and by staff), keep a history, send e-mails, can be cancelled or returned, have PDF receipts, and prices show in the visitor's currency (PKR in Pakistan).

**Architecture:** A detailed `stage` drives the existing coarse `status` that rules, chat and AI read. `storefront/lifecycle.py` is the only place that changes a stage (writes an `OrderEvent`); async services in `storefront/order_service.py` load orders and customers, call the lifecycle and queue e-mails. The Settings tick runs two new jobs (order progress, exchange rates). Prices stay USD in the database; each order stores the currency, rate and local amount at checkout; the web converts with `/currency` rates and a `currency` cookie set by the edge proxy from Vercel's country header.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, Pydantic 2, httpx, ReportLab, pytest (real PostgreSQL), Next.js 16, TanStack Query, generated `@hey-api` client.

**Spec:** `docs/superpowers/specs/2026-09-28-orders-and-currency-design.md`

## Global Constraints

- Stages: `placed, packed, shipped, out_for_delivery, delivered, lost, cancelled, return_requested, return_refused, returned`.
- Status mapping: placed/packed → processing; shipped/out_for_delivery → shipped; delivered/return_requested/return_refused → delivered; lost → lost; cancelled → cancelled; returned → returned.
- Allowed moves: placed→packed|cancelled; packed→shipped|cancelled; shipped→out_for_delivery|lost; out_for_delivery→delivered|lost; delivered→return_requested; return_requested→returned|return_refused. Anything else → 409.
- Only shop orders (`checkout_ref` not null) move. Dataset orders never move.
- Delays never change `committed_delivery_date`; they set `expected_delivery_date`.
- Return window: `storefront_config().returns.window_days` (30) days after `delivered_date`; reason 10–500 characters.
- Settings `orders` group: auto_advance (true), step_minutes 1–1440 (2), delay_chance_pct 0–100 (10), lost_chance_pct 0–20 (0), emails (true), fallback_pkr_rate 1–10000 (280).
- Currencies: USD ($, 2), PKR (Rs, 0), EUR (€, 2), GBP (£, 2), AED (AED, 2). Rates URL `https://open.er-api.com/v6/latest/USD`, refreshed every 12 h.
- Prices, policies, rules, analytics and the AI keep using USD `amount`.
- Python: ruff, ruff format (Python paths only — never `ruff format .`, it rewrites Markdown), `mypy --strict`. Web: ESLint, tsc, `next build`.
- Commit after each task; no `Co-Authored-By` line.

## Review Focus

- A customer opens another customer's order (cancel, return, events, receipt) by guessing the ref → 404, never the data (tests in Tasks 8).
- Two ticks overlap and pick the same order → it moves one step only (row lock `skip_locked`; test in Task 6).
- A delayed order is delivered → it counts as late only if delivered after the promise; the promise is unchanged by the delay (test in Task 3).
- The exchange-rate service is down at the first ever start (no stored rates) → PKR still works with the fallback rate; other currencies fall back to USD display (test in Task 4).
- Checkout in PKR → the order's local amount is rounded to whole rupees and the receipt shows that exact amount (tests in Tasks 5 and 8).

---

## File Structure

| File | Responsibility |
|---|---|
| `app_settings/model.py`, `defaults.py` | `OrderSettings` group |
| `database/models/complaints.py` | `Order` new columns; `OrderEvent` |
| `database/models/storefront.py` | `FxRate` |
| `database/models/email.py` | `OutboundEmail.order_id` |
| `storefront/lifecycle.py` | stages, mapping, `move`, `delay`, `deliver_late` |
| `storefront/currency.py` | currencies, rounding, fetch/refresh/current rates |
| `storefront/automation.py` | `advance_due_orders` |
| `storefront/order_emails.py` + `config/order_emails.yaml` | order e-mail texts and queueing |
| `storefront/order_service.py` | async customer/staff actions |
| `storefront/receipt.py` | PDF receipt |
| `src/api/routes/orders.py` | customer order actions, receipt, staff orders API, `/currency` |
| `web/src/lib/currency.tsx` | `CurrencyProvider`, `useCurrency`, `Price`, `formatLocal` |
| `web/src/components/shop/currency-switcher.tsx` | header switcher |
| `web/src/components/shop/order-tracker.tsx` | customer tracker, history, actions |
| `web/src/app/(app)/fulfilment/page.tsx`, `web/src/components/fulfilment/*` | staff Orders page |

---

### Task 1: Orders settings group

**Files:**
- Modify: `app_settings/model.py`, `app_settings/defaults.py`, `app_settings/__init__.py`, `src/api/schemas.py` (`SettingsUpdate`)
- Modify tests: `tests/integration/test_settings_api.py` (`body`), `tests/integration/test_branding_api.py` (payload)
- Test: `tests/unit/test_app_settings_model.py`

**Interfaces:**
- Produces: `OrderSettings(auto_advance: bool, step_minutes: int, delay_chance_pct: int, lost_chance_pct: int, emails: bool, fallback_pkr_rate: float)`; `RuntimeSettings.orders`; `SettingsUpdate.orders`.

- [ ] **Step 1: Failing tests** (append to `tests/unit/test_app_settings_model.py`)

```python
def test_order_defaults() -> None:
    o = defaults().orders
    assert (o.auto_advance, o.step_minutes, o.delay_chance_pct, o.lost_chance_pct) == (
        True,
        2,
        10,
        0,
    )
    assert o.emails and o.fallback_pkr_rate == 280


@pytest.mark.parametrize(
    ("field", "value"),
    [("step_minutes", 0), ("delay_chance_pct", 101), ("lost_chance_pct", 21), ("fallback_pkr_rate", 0)],
)
def test_order_limits(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        RuntimeSettings.model_validate(with_group("orders", **{field: value}))
```

- [ ] **Step 2: Run** `uv run pytest -q tests/unit/test_app_settings_model.py` — Expected: FAIL (`'RuntimeSettings' object has no attribute 'orders'`).

- [ ] **Step 3: Implement**

`app_settings/model.py` (before `RuntimeSettings`):

```python
class OrderSettings(_Group):
    auto_advance: bool
    step_minutes: int = Field(ge=1, le=1440)
    delay_chance_pct: int = Field(ge=0, le=100)
    lost_chance_pct: int = Field(ge=0, le=20)
    emails: bool
    fallback_pkr_rate: float = Field(ge=1, le=10000)
```

and in `RuntimeSettings` add `orders: OrderSettings`.
`app_settings/defaults.py` — add to the validated dict:

```python
            "orders": {
                "auto_advance": True,
                "step_minutes": 2,
                "delay_chance_pct": 10,
                "lost_chance_pct": 0,
                "emails": True,
                "fallback_pkr_rate": 280.0,
            },
```

`src/api/schemas.py` `SettingsUpdate`: add `orders: OrderSettings` (import from `app_settings.model`).
`src/api/routes/settings.py` `update_settings`: pass `orders=payload.orders` to `RuntimeSettings(...)`.
Tests: in `tests/integration/test_settings_api.py` `body()` change the group tuple to
`("email", "ai", "operations", "orders")`; in `tests/integration/test_branding_api.py` add
`"orders": s["orders"]` to the payload.

- [ ] **Step 4: Run** `uv run pytest -q tests/unit/test_app_settings_model.py tests/integration/test_settings_api.py tests/integration/test_branding_api.py && uv run pytest -q` — Expected: PASS.

- [ ] **Step 5: Commit** `git commit -m "feat(settings): orders settings group"` (add the changed files).

---

### Task 2: Order data model

**Files:**
- Modify: `database/models/complaints.py` (`Order`, new `OrderEvent`), `database/models/storefront.py` (`FxRate`), `database/models/email.py` (`OutboundEmail.order_id`), `database/models/__init__.py`
- Create: migration `database/migrations/versions/20260929_<rev>_orders_lifecycle.py`
- Test: `tests/integration/test_order_models.py`

**Interfaces:**
- Produces: `Order.stage: str`, `Order.next_step_at: datetime | None`, `Order.manual_hold: bool`, `Order.expected_delivery_date: date | None`, `Order.emails_sent: list[str]`, `Order.currency: str`, `Order.fx_rate: Decimal`, `Order.amount_local: Decimal | None`, `Order.events` (relationship, ordered by `created_at`); `OrderEvent(order_id, stage, note, actor, actor_user_id, created_at)`; `FxRate(currency, rate, fetched_at)`; `OutboundEmail.order_id`.

- [ ] **Step 1: Failing test**

```python
"""New order columns and events persist with sensible defaults."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from database.models import Customer, CustomerType, Order, OrderEvent
from database.session import sync_session

pytestmark = pytest.mark.db


def test_order_defaults_and_events(clean_db: None) -> None:
    with sync_session() as db:
        customer = Customer(customer_ref="CUST-990001", full_name="Ada", customer_type=CustomerType.STANDARD)
        db.add(customer)
        db.flush()
        order = Order(
            order_ref="ORD-990001", customer_id=customer.id, product_name="Pulse 700",
            product_category="audio", amount=Decimal("279.00"), order_date=date(2026, 9, 29),
            committed_delivery_date=date(2026, 10, 6),
        )  # fmt: skip
        db.add(order)
        db.flush()
        db.add(OrderEvent(order_id=order.id, stage="placed", actor="customer"))
    with sync_session() as db:
        order = db.scalars(select(Order).where(Order.order_ref == "ORD-990001")).one()
        assert (order.stage, order.currency, order.fx_rate, order.manual_hold) == (
            "placed", "USD", Decimal("1"), False,
        )  # fmt: skip
        assert order.emails_sent == [] and order.expected_delivery_date is None
        assert [e.stage for e in order.events] == ["placed"]
```

(Check `CustomerType` export and `Customer` required fields with `grep -n "class Customer" -A20 database/models/complaints.py`; add fields the model requires.)

- [ ] **Step 2: Run** `uv run pytest -q tests/integration/test_order_models.py` — Expected: FAIL (`ImportError: OrderEvent`).

- [ ] **Step 3: Models**

In `Order` (after `checkout_ref`):

```python
    # Lifecycle (shop orders; dataset orders keep the stage that mirrors their status).
    stage: Mapped[str] = mapped_column(String(24), default="placed", server_default="placed")
    next_step_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    manual_hold: Mapped[bool] = mapped_column(default=False, server_default="false")
    expected_delivery_date: Mapped[date | None] = mapped_column(Date)
    emails_sent: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    # What the customer saw at checkout; `amount` stays USD for policies and analytics.
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    fx_rate: Mapped[Decimal] = mapped_column(Numeric(14, 6), default=Decimal("1"), server_default="1")
    amount_local: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))

    events: Mapped[list["OrderEvent"]] = relationship(
        order_by="OrderEvent.created_at", cascade="all, delete-orphan"
    )
```

New class after `Order`:

```python
class OrderEvent(UUIDPrimaryKeyMixin, Base):
    """One step in an order's history (a stage change or a delay)."""

    __tablename__ = "order_events"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(24))  # a stage, or "delayed"
    note: Mapped[str | None] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(String(10))  # system | staff | customer
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(UTC)
    )
```

(import `JSONB`, `func`, `UTC`, `Text` as needed.)
`database/models/storefront.py`:

```python
class FxRate(Base):
    """USD → currency rate from the daily exchange-rate refresh."""

    __tablename__ = "fx_rates"

    currency: Mapped[str] = mapped_column(String(3), primary_key=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(14, 6))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
```

`database/models/email.py` `OutboundEmail`: `order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id"), index=True)`.
Export `OrderEvent`, `FxRate` in `database/models/__init__.py`.

- [ ] **Step 4: Migration**

Run `uv run alembic revision --autogenerate -m "orders lifecycle"`, rename to `20260929_<rev>_orders_lifecycle.py`, remove unused imports, and append to `upgrade()`:

```python
    op.execute(
        "UPDATE orders SET stage = CASE status WHEN 'processing' THEN 'placed' "
        "WHEN 'shipped' THEN 'shipped' WHEN 'lost' THEN 'lost' WHEN 'returned' THEN 'returned' "
        "ELSE 'delivered' END, amount_local = amount"
    )
```

Run `uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head` — Expected: no errors.

- [ ] **Step 5: Run** `uv run pytest -q tests/integration/test_order_models.py && uv run pytest -q` — Expected: PASS.

- [ ] **Step 6: Commit** `git commit -m "feat(orders): stage, history, currency and rate columns"`.

---

### Task 3: Lifecycle rules

**Files:**
- Create: `storefront/lifecycle.py`
- Modify: `complaint_rules/facts.py` (order_status vocabulary adds `cancelled`)
- Test: `tests/unit/test_order_lifecycle.py`

**Interfaces:**
- Consumes: `Order`, `OrderEvent` (Task 2).
- Produces: `STAGES`, `STATUS_OF: dict[str, str]`, `FORWARD: dict[str, str]`, `MOVING: tuple[str, ...]`, `LifecycleError(message, stage)`, `move(db, order, to, actor, *, user_id=None, note=None, now=None) -> OrderEvent`, `delay(db, order, expected, actor, *, user_id=None, note=None, now=None) -> OrderEvent`, `deliver_late(db, order, days_late, *, user_id, now=None) -> OrderEvent`. `db` is anything with `.add()`.

- [ ] **Step 1: Failing tests**

```python
"""Order stages: allowed moves, status mapping, history, delays never move the promise."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from database.models import Order
from storefront.lifecycle import STATUS_OF, LifecycleError, delay, deliver_late, move

NOW = datetime(2026, 9, 29, 10, 0, tzinfo=UTC)


class Db:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, obj: object) -> None:
        self.added.append(obj)


def order(stage: str = "placed", shop: bool = True) -> Order:
    return Order(
        order_ref="ORD-800100", stage=stage, status=STATUS_OF[stage],
        checkout_ref="CHK-1" if shop else None, product_name="Pulse 700",
        product_category="audio", amount=Decimal("279"), order_date=date(2026, 9, 21),
        committed_delivery_date=date(2026, 9, 28), emails_sent=[],
    )  # fmt: skip


def test_the_happy_path_and_status_mapping() -> None:
    o, db = order(), Db()
    for stage, status in [("packed", "processing"), ("shipped", "shipped"),
                          ("out_for_delivery", "shipped"), ("delivered", "delivered")]:  # fmt: skip
        move(db, o, stage, "system", now=NOW)
        assert (o.stage, o.status) == (stage, status)
    assert o.delivered_date == NOW.date() and o.next_step_at is None
    assert [e.stage for e in db.added] == ["packed", "shipped", "out_for_delivery", "delivered"]


@pytest.mark.parametrize(("start", "to"), [("placed", "shipped"), ("shipped", "cancelled"),
                                           ("delivered", "packed"), ("returned", "return_requested")])  # fmt: skip
def test_illegal_moves_are_refused(start: str, to: str) -> None:
    with pytest.raises(LifecycleError):
        move(Db(), order(start), to, "staff", now=NOW)


def test_dataset_orders_never_move() -> None:
    with pytest.raises(LifecycleError):
        move(Db(), order("placed", shop=False), "packed", "system", now=NOW)


def test_a_delay_sets_the_expected_date_and_keeps_the_promise() -> None:
    o, db = order("shipped"), Db()
    delay(db, o, date(2026, 10, 2), "system", now=NOW)
    assert o.committed_delivery_date == date(2026, 9, 28)  # the promise
    assert o.expected_delivery_date == date(2026, 10, 2)
    assert db.added[-1].stage == "delayed"  # type: ignore[attr-defined]
    with pytest.raises(LifecycleError):
        delay(Db(), order("placed"), date(2026, 10, 2), "system", now=NOW)


def test_late_delivery_shifts_the_timeline() -> None:
    o, db = order("out_for_delivery"), Db()
    deliver_late(db, o, 3, user_id=None, now=NOW)
    assert o.stage == "delivered" and o.delivered_date == NOW.date()
    assert o.committed_delivery_date == date(2026, 9, 24)  # 3 business days before Tue 29 Sep
    assert "3 business days late" in (db.added[-1].note or "")  # type: ignore[attr-defined]
```

- [ ] **Step 2: Run** `uv run pytest -q tests/unit/test_order_lifecycle.py` — Expected: FAIL (`No module named 'storefront.lifecycle'`).

- [ ] **Step 3: Implement `storefront/lifecycle.py`**

```python
"""The only place an order's stage changes: allowed moves, status mapping and history."""

import uuid
from datetime import UTC, date, datetime
from typing import Literal, Protocol

from database.models import Order, OrderEvent
from storefront.orders import SHIPPING_DAYS, subtract_business_days

STAGES = (
    "placed", "packed", "shipped", "out_for_delivery", "delivered",
    "lost", "cancelled", "return_requested", "return_refused", "returned",
)  # fmt: skip
STATUS_OF = {
    "placed": "processing", "packed": "processing", "shipped": "shipped",
    "out_for_delivery": "shipped", "delivered": "delivered", "lost": "lost",
    "cancelled": "cancelled", "return_requested": "delivered",
    "return_refused": "delivered", "returned": "returned",
}  # fmt: skip
FORWARD = {"placed": "packed", "packed": "shipped", "shipped": "out_for_delivery",
           "out_for_delivery": "delivered"}  # fmt: skip
ALLOWED: dict[str, set[str]] = {
    "placed": {"packed", "cancelled"},
    "packed": {"shipped", "cancelled"},
    "shipped": {"out_for_delivery", "lost"},
    "out_for_delivery": {"delivered", "lost"},
    "delivered": {"return_requested"},
    "return_requested": {"returned", "return_refused"},
}
MOVING = ("placed", "packed", "shipped", "out_for_delivery")
LABELS = {s: s.replace("_", " ") for s in STAGES}
Actor = Literal["system", "staff", "customer"]


class Adder(Protocol):
    def add(self, instance: object) -> None: ...


class LifecycleError(ValueError):
    def __init__(self, message: str, stage: str):
        super().__init__(message)
        self.stage = stage


def _event(db: Adder, order: Order, stage: str, actor: Actor, user_id: uuid.UUID | None,
           note: str | None, now: datetime) -> OrderEvent:  # fmt: skip
    event = OrderEvent(order_id=order.id, stage=stage, note=note, actor=actor,
                       actor_user_id=user_id, created_at=now)  # fmt: skip
    db.add(event)
    return event


def move(
    db: Adder, order: Order, to: str, actor: Actor, *,
    user_id: uuid.UUID | None = None, note: str | None = None, now: datetime | None = None,
) -> OrderEvent:  # fmt: skip
    if order.checkout_ref is None:
        raise LifecycleError("Only orders placed in the shop move.", order.stage)
    if to not in ALLOWED.get(order.stage, set()):
        raise LifecycleError(
            f"An order that is {LABELS[order.stage]} cannot become {LABELS.get(to, to)}.",
            order.stage,
        )
    now = now or datetime.now(UTC)
    order.stage, order.status = to, STATUS_OF[to]
    if to == "delivered":
        order.delivered_date = now.date()
    if to not in MOVING:
        order.next_step_at = None
    return _event(db, order, to, actor, user_id, note, now)


def delay(
    db: Adder, order: Order, expected: date, actor: Actor, *,
    user_id: uuid.UUID | None = None, note: str | None = None, now: datetime | None = None,
) -> OrderEvent:  # fmt: skip
    if order.stage not in ("shipped", "out_for_delivery"):
        raise LifecycleError("Only orders on their way can be delayed.", order.stage)
    if expected <= order.committed_delivery_date:
        raise LifecycleError("The new date must be after the promised date.", order.stage)
    order.expected_delivery_date = expected
    text = f"Delayed: now expected {expected:%d %b %Y}" + (f". {note}" if note else "")
    return _event(db, order, "delayed", actor, user_id, text, now or datetime.now(UTC))


def deliver_late(
    db: Adder, order: Order, days_late: int, *, user_id: uuid.UUID | None,
    now: datetime | None = None,
) -> OrderEvent:  # fmt: skip
    """Demo timeline: promised `days_late` business days before today, delivered today."""
    now = now or datetime.now(UTC)
    promised = subtract_business_days(now.date(), days_late)
    order.committed_delivery_date = promised
    order.order_date = subtract_business_days(promised, SHIPPING_DAYS.get(order.shipping_method, 5))
    note = f"Delivered {days_late} business day{'s' if days_late != 1 else ''} late (demo timeline)"
    return move(db, order, "delivered", "staff", user_id=user_id, note=note, now=now)
```

`complaint_rules/facts.py` line 29: change the description to `"processing, shipped, delivered, lost, returned or cancelled"`.

- [ ] **Step 4: Run** `uv run pytest -q tests/unit/test_order_lifecycle.py && uv run pytest -q` — Expected: PASS. (If `Order()` in the test needs `shipping_method`, it defaults to "standard".)

- [ ] **Step 5: Commit** `git commit -m "feat(orders): lifecycle rules and history"`.

---

### Task 4: Currency and exchange rates

**Files:**
- Create: `storefront/currency.py`, `tests/unit/test_currency.py`, `tests/integration/test_currency_api.py`
- Modify: `app_settings/jobs.py` (job `fx-refresh`), `src/api/routes/storefront.py` (`GET /currency`), `src/api/schemas.py` (`CurrencyOut`, `CurrencyInfo`)

**Interfaces:**
- Produces: `CURRENCIES: dict[str, Currency]` (`Currency(code, symbol, decimals)`), `to_local(usd: Decimal, rate: Decimal, code: str) -> Decimal`, `fetch_rates(client: httpx.Client | None = None) -> dict[str, Decimal]`, `RatesError`, `refresh_rates(client=None, now=None) -> int`, `current_rates(db: Session) -> dict[str, Decimal]`, `async current_rates_async(db: AsyncSession) -> dict[str, Decimal]`; `GET /api/v1/currency` → `CurrencyOut`.

- [ ] **Step 1: Failing unit tests**

```python
"""Currencies: rounding per currency and parsing the rates service."""

from decimal import Decimal

import httpx
import pytest

from storefront.currency import CURRENCIES, RatesError, fetch_rates, to_local


def test_pkr_rounds_to_whole_rupees_and_others_to_cents() -> None:
    assert to_local(Decimal("279.00"), Decimal("281.4"), "PKR") == Decimal("78511")
    assert to_local(Decimal("279.00"), Decimal("0.92"), "EUR") == Decimal("256.68")
    assert CURRENCIES["PKR"].decimals == 0 and CURRENCIES["USD"].symbol == "$"


def client(status: int, body: object) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(status, json=body)))


def test_fetch_keeps_only_supported_currencies() -> None:
    body = {"result": "success", "rates": {"USD": 1, "PKR": 281.4, "EUR": 0.92, "JPY": 150}}
    assert fetch_rates(client(200, body)) == {"USD": Decimal("1"), "PKR": Decimal("281.4"), "EUR": Decimal("0.92")}


@pytest.mark.parametrize(("status", "body"), [(500, {}), (200, {"result": "error"})])
def test_fetch_failures_raise(status: int, body: object) -> None:
    with pytest.raises(RatesError):
        fetch_rates(client(status, body))
```

- [ ] **Step 2: Failing integration tests**

```python
"""Rates are stored, survive a failed refresh, fall back for PKR, and are public."""

from decimal import Decimal

import httpx
import pytest

from database.session import sync_session
from storefront.currency import current_rates, refresh_rates
from tests.fixtures.settings import use_settings

pytestmark = pytest.mark.db
OK = {"result": "success", "rates": {"PKR": 281.4, "EUR": 0.92, "GBP": 0.79, "AED": 3.67}}


def client(ok: bool) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json=OK) if ok else httpx.Response(503)))  # fmt: skip


def test_no_rates_yet_uses_the_pkr_fallback(clean_db: None) -> None:
    use_settings(orders={"fallback_pkr_rate": 300.0})
    with sync_session() as db:
        assert current_rates(db) == {"USD": Decimal("1"), "PKR": Decimal("300")}


def test_refresh_stores_and_a_failure_keeps_them(clean_db: None) -> None:
    assert refresh_rates(client(True)) == 4
    assert refresh_rates(client(False)) == 0
    with sync_session() as db:
        assert current_rates(db)["PKR"] == Decimal("281.4")


async def test_currency_endpoint_is_public(client: httpx.AsyncClient) -> None:
    body = (await client.get("/api/v1/currency")).json()
    assert body["rates"]["USD"] == 1 and "PKR" in body["rates"]
    assert {c["code"] for c in body["currencies"]} == {"USD", "PKR", "EUR", "GBP", "AED"}
```

- [ ] **Step 3: Run** both files — Expected: FAIL (`No module named 'storefront.currency'`).

- [ ] **Step 4: Implement `storefront/currency.py`**

```python
"""Local currencies: prices stay USD; visitors see their currency at the day's rate."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import app_settings
from database.models import FxRate
from database.session import sync_session
from src.core.logging import get_logger

log = get_logger(__name__)
RATES_URL = "https://open.er-api.com/v6/latest/USD"


@dataclass(frozen=True)
class Currency:
    code: str
    symbol: str
    decimals: int


CURRENCIES = {
    "USD": Currency("USD", "$", 2),
    "PKR": Currency("PKR", "Rs", 0),
    "EUR": Currency("EUR", "€", 2),
    "GBP": Currency("GBP", "£", 2),
    "AED": Currency("AED", "AED", 2),
}


class RatesError(RuntimeError):
    pass


def to_local(usd: Decimal, rate: Decimal, code: str) -> Decimal:
    places = Decimal(1).scaleb(-CURRENCIES[code].decimals)
    return (usd * rate).quantize(places, rounding=ROUND_HALF_UP)


def fetch_rates(client: httpx.Client | None = None) -> dict[str, Decimal]:
    http = client or httpx.Client(timeout=10)
    try:
        response = http.get(RATES_URL)
        body = response.json() if response.status_code == 200 else {}
    except (httpx.HTTPError, ValueError) as exc:
        raise RatesError(str(exc)) from exc
    if body.get("result") != "success":
        raise RatesError(f"rates service answered {response.status_code}")
    rates = body.get("rates") or {}
    return {code: Decimal(str(rates[code])) for code in CURRENCIES if code in rates}


def refresh_rates(client: httpx.Client | None = None, now: datetime | None = None) -> int:
    """Store the day's rates; on failure keep the last ones. Returns how many were stored."""
    try:
        rates = fetch_rates(client)
    except RatesError as exc:
        log.warning("fx.refresh_failed", error=str(exc))
        return 0
    now = now or datetime.now(UTC)
    rows = [{"currency": c, "rate": r, "fetched_at": now} for c, r in rates.items() if c != "USD"]
    with sync_session() as db:
        for row in rows:
            db.execute(insert(FxRate).values(**row).on_conflict_do_update(
                index_elements=[FxRate.currency], set_={"rate": row["rate"], "fetched_at": now}))  # fmt: skip
    return len(rows)


def _with_fallback(stored: dict[str, Decimal]) -> dict[str, Decimal]:
    rates = {"USD": Decimal("1"), **stored}
    if "PKR" not in rates:
        rates["PKR"] = Decimal(str(app_settings.runtime().orders.fallback_pkr_rate))
    return rates


def current_rates(db: Session) -> dict[str, Decimal]:
    return _with_fallback({r.currency: r.rate for r in db.scalars(select(FxRate))})


async def current_rates_async(db: AsyncSession) -> dict[str, Decimal]:
    return _with_fallback({r.currency: r.rate for r in await db.scalars(select(FxRate))})
```

Schemas (`src/api/schemas.py`):

```python
class CurrencyInfo(BaseModel):
    code: str
    symbol: str
    decimals: int


class CurrencyOut(BaseModel):
    rates: dict[str, float]
    fetched_at: datetime | None
    currencies: list[CurrencyInfo]
```

Route in `src/api/routes/storefront.py`:

```python
@router.get("/currency", response_model=CurrencyOut)
async def currency_rates(db: AsyncSession = Depends(get_db)) -> CurrencyOut:
    rates = await current_rates_async(db)
    fetched = await db.scalar(select(func.max(FxRate.fetched_at)))
    return CurrencyOut(
        rates={c: float(r) for c, r in rates.items()},
        fetched_at=fetched,
        currencies=[CurrencyInfo(code=c.code, symbol=c.symbol, decimals=c.decimals) for c in CURRENCIES.values()],
    )
```

Job in `app_settings/jobs.py`:

```python
def _fx() -> object:
    from storefront.currency import refresh_rates

    return refresh_rates()
```

and `"fx-refresh": Job(lambda s: 12 * 3600, _fx)` in `JOBS`.

- [ ] **Step 5: Run** `uv run pytest -q tests/unit/test_currency.py tests/integration/test_currency_api.py && uv run pytest -q` — Expected: PASS.

- [ ] **Step 6: Commit** `git commit -m "feat(orders): exchange rates and local currency amounts"`.

---

### Task 5: Checkout in the visitor's currency

**Files:**
- Modify: `storefront/orders.py` (`checkout`), `src/api/routes/storefront.py` (`place_order`), `src/api/schemas.py` (`CheckoutIn.currency`, `ShopOrderOut` new fields)
- Create: `tests/fixtures/shop.py`
- Test: `tests/integration/test_checkout_currency.py`

**Interfaces:**
- Consumes: `current_rates_async`, `to_local`, `CURRENCIES` (Task 4); `OrderEvent` (Task 2).
- Produces: `checkout(db, customer, lines, shipping_method, today, *, currency="USD", rates, now)`; `ShopOrderOut` adds `stage, currency, fx_rate, amount_local, expected_delivery_date, next_step_at`; test helpers `shopper(create_user, make_token, email) -> dict[str, str]`, `async place_order(client, headers, sku="VH-AUD-P700", currency="USD") -> dict`.

- [ ] **Step 1: Helper `tests/fixtures/shop.py`**

```python
"""A signed-in shopper and an order placed through the real checkout."""

from collections.abc import Callable
from typing import Any

import httpx

from database.models import Role, User


def shopper(create_user: Callable[..., User], make_token: Callable[..., str],
            email: str = "shopper@example.test") -> dict[str, str]:  # fmt: skip
    user = create_user(Role.CUSTOMER, email=email)
    return {"Authorization": f"Bearer {make_token(user.clerk_user_id)}"}


async def place_order(client: httpx.AsyncClient, headers: dict[str, str],
                      sku: str = "VH-AUD-P700", currency: str = "USD") -> dict[str, Any]:  # fmt: skip
    response = await client.post(
        "/api/v1/checkout",
        headers=headers,
        json={"lines": [{"sku": sku, "quantity": 1}], "currency": currency},
    )
    assert response.status_code == 201, response.text
    order: dict[str, Any] = response.json()[0]
    return order
```

- [ ] **Step 2: Failing tests**

```python
"""Checkout stores the currency, rate and local amount, and starts the lifecycle."""

from collections.abc import Callable
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from database.models import FxRate, Order, User
from database.session import sync_session
from tests.fixtures.shop import place_order, shopper

pytestmark = pytest.mark.db


async def test_checkout_in_pkr_records_the_rate_and_rounded_amount(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str]
) -> None:
    from datetime import UTC, datetime

    with sync_session() as db:
        db.add(FxRate(currency="PKR", rate=Decimal("281.4"), fetched_at=datetime.now(UTC)))
    order = await place_order(client, shopper(create_user, make_token), currency="PKR")
    assert (order["currency"], order["stage"], order["status"]) == ("PKR", "placed", "processing")
    assert Decimal(str(order["amount_local"])) == Decimal("78511")  # 279 × 281.4, whole rupees
    assert order["amount"] == 279.0 and order["next_step_at"] is not None
    with sync_session() as db:
        saved = db.scalars(select(Order).where(Order.order_ref == order["order_ref"])).one()
        assert [e.stage for e in saved.events] == ["placed"]


async def test_unknown_currency_is_refused(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str]
) -> None:
    response = await client.post(
        "/api/v1/checkout", headers=shopper(create_user, make_token),
        json={"lines": [{"sku": "VH-AUD-P700", "quantity": 1}], "currency": "JPY"},
    )  # fmt: skip
    assert response.status_code == 422
```

- [ ] **Step 3: Run** — Expected: FAIL (no `currency` in response).

- [ ] **Step 4: Implement**

`CheckoutIn`: `currency: Literal["USD", "PKR", "EUR", "GBP", "AED"] = "USD"`.
`ShopOrderOut` add: `stage: str`, `currency: str`, `fx_rate: float`, `amount_local: float | None`, `expected_delivery_date: date | None`, `next_step_at: datetime | None`.
`storefront/orders.checkout` signature gains `*, currency: str = "USD", rates: dict[str, Decimal] | None = None, now: datetime | None = None`, and in the order construction:

```python
    rates = rates or {"USD": Decimal("1")}
    rate = rates.get(currency) or Decimal("1")
    if currency not in rates:
        currency = "USD"  # no rate yet: charge and show in USD
    now = now or datetime.now(UTC)
    step = timedelta(minutes=app_settings.runtime().orders.step_minutes)
```

and per order: `stage="placed", currency=currency, fx_rate=rate, amount_local=to_local(order_amount, rate, currency), next_step_at=now + step`, then after `db.add(order)` and before the loop ends: `db.add(OrderEvent(order_id=..., ...))` — do it after `await db.flush()`:

```python
    await db.flush()
    for order in orders:
        db.add(OrderEvent(order_id=order.id, stage="placed", actor="customer", created_at=now))
```

`place_order` route: `rates = await current_rates_async(db)` and pass `currency=payload.currency, rates=rates`.

- [ ] **Step 5: Run** `uv run pytest -q tests/integration/test_checkout_currency.py tests/integration/test_storefront_api.py && uv run pytest -q` — Expected: PASS.

- [ ] **Step 6: Commit** `git commit -m "feat(orders): checkout in the visitor's currency starts the lifecycle"`.

---

### Task 6: Automatic progress

**Files:**
- Create: `storefront/automation.py`
- Modify: `app_settings/jobs.py` (job `order-progress`)
- Test: `tests/integration/test_order_automation.py`

**Interfaces:**
- Consumes: `move`, `delay`, `FORWARD`, `MOVING` (Task 3); `runtime().orders` (Task 1); `queue_order_email` is added in Task 7 (this task does not call it).
- Produces: `advance_due_orders(now: datetime | None = None, rng: random.Random | None = None) -> list[str]`.

- [ ] **Step 1: Failing tests**

```python
"""The courier simulation: only due, not-held shop orders move; seeded delays and losses."""

import random
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select, update

from database.models import Order, User
from database.session import sync_session
from storefront.automation import advance_due_orders
from tests.fixtures.settings import use_settings
from tests.fixtures.shop import place_order, shopper

pytestmark = pytest.mark.db
LATER = datetime.now(UTC) + timedelta(hours=1)


def stage(ref: str) -> str:
    with sync_session() as db:
        return db.scalars(select(Order.stage).where(Order.order_ref == ref)).one()


async def test_due_orders_move_one_step(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str]
) -> None:
    use_settings(orders={"delay_chance_pct": 0, "lost_chance_pct": 0})
    ref = (await place_order(client, shopper(create_user, make_token)))["order_ref"]
    assert advance_due_orders(datetime.now(UTC)) == []  # not due yet
    assert advance_due_orders(LATER) == [ref] and stage(ref) == "packed"
    assert advance_due_orders(LATER) == []  # next step is step_minutes after LATER


async def test_held_orders_and_switched_off_automation_do_not_move(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str]
) -> None:
    ref = (await place_order(client, shopper(create_user, make_token)))["order_ref"]
    with sync_session() as db:
        db.execute(update(Order).where(Order.order_ref == ref).values(manual_hold=True))
    assert advance_due_orders(LATER) == []
    with sync_session() as db:
        db.execute(update(Order).where(Order.order_ref == ref).values(manual_hold=False))
    use_settings(orders={"auto_advance": False})
    assert advance_due_orders(LATER) == []


async def test_seeded_delay_then_delivery(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str]
) -> None:
    use_settings(orders={"delay_chance_pct": 100, "lost_chance_pct": 0, "step_minutes": 1})
    ref = (await place_order(client, shopper(create_user, make_token)))["order_ref"]
    now = LATER
    for _ in range(12):
        advance_due_orders(now, random.Random(1))
        now += timedelta(minutes=5)
    with sync_session() as db:
        order = db.scalars(select(Order).where(Order.order_ref == ref)).one()
        assert order.stage == "delivered" and order.expected_delivery_date is not None
        assert "delayed" in [e.stage for e in order.events]
```

- [ ] **Step 2: Run** — Expected: FAIL (`No module named 'storefront.automation'`).

- [ ] **Step 3: Implement `storefront/automation.py`**

```python
"""The courier simulation: due shop orders advance one step (run by the Settings tick)."""

import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

import app_settings
from database.models import Order
from database.session import sync_session
from src.core.logging import get_logger
from storefront.lifecycle import FORWARD, MOVING, delay, move
from storefront.orders import add_business_days

log = get_logger(__name__)
BATCH = 50
DELAY_WAIT_STEPS = 3


def advance_due_orders(now: datetime | None = None, rng: random.Random | None = None) -> list[str]:
    cfg = app_settings.runtime().orders
    if not cfg.auto_advance:
        return []
    now, rng = now or datetime.now(UTC), rng or random.Random()
    step = timedelta(minutes=cfg.step_minutes)
    moved: list[str] = []
    with sync_session() as db:
        orders = db.scalars(
            select(Order)
            .where(
                Order.checkout_ref.is_not(None),
                Order.stage.in_(MOVING),
                Order.manual_hold.is_(False),
                Order.next_step_at <= now,
            )
            .order_by(Order.next_step_at)
            .limit(BATCH)
            .with_for_update(skip_locked=True)  # overlapping ticks never move an order twice
        ).all()
        for order in orders:
            try:
                with db.begin_nested():
                    wait = step
                    if (order.stage == "shipped" and order.expected_delivery_date is None
                            and rng.random() * 100 < cfg.delay_chance_pct):  # fmt: skip
                        expected = add_business_days(order.committed_delivery_date, rng.randint(2, 5))
                        delay(db, order, expected, "system", now=now)
                        wait = step * DELAY_WAIT_STEPS
                    target = FORWARD[order.stage]
                    if order.stage == "out_for_delivery" and rng.random() * 100 < cfg.lost_chance_pct:
                        target = "lost"
                    move(db, order, target, "system", now=now)
                    if order.stage in MOVING:
                        order.next_step_at = now + wait
                moved.append(order.order_ref)
            except Exception:  # one broken order never stops the batch
                log.exception("orders.advance_failed", order=order.order_ref)
    return moved
```

Job in `app_settings/jobs.py`:

```python
def _orders() -> object:
    from storefront.automation import advance_due_orders

    return advance_due_orders()
```

and `"order-progress": Job(lambda s: 30, _orders)` in `JOBS`. Update
`tests/integration/test_mailbox_tasks.py::test_mailbox_jobs_run_from_the_settings_tick` expectation
set to include `"order-progress", "fx-refresh"` only if it compares equality (it uses `<=`; leave it).

- [ ] **Step 4: Run** `uv run pytest -q tests/integration/test_order_automation.py && uv run pytest -q` — Expected: PASS.

- [ ] **Step 5: Commit** `git commit -m "feat(orders): automatic progress with seeded delays and losses"`.

---

### Task 7: Order e-mails

**Files:**
- Create: `config/order_emails.yaml`, `storefront/order_emails.py`
- Modify: `email_channel/outbound.py` (`queue` gains `order_id: uuid.UUID | None = None`), `storefront/automation.py` (queue after each move/delay)
- Test: `tests/integration/test_order_emails.py`

**Interfaces:**
- Consumes: `Order`, `Customer`, `OutboundEmail.order_id`, `queue`, `runtime().orders.emails`, `runtime().branding.shop_name`, `CURRENCIES`.
- Produces: `EMAIL_KINDS`, `queue_order_email(db, order, customer, kind) -> OutboundEmail | None`, `format_amount(order) -> str`.

- [ ] **Step 1: `config/order_emails.yaml`**

```yaml
# Order e-mails. Placeholders: {name} {order_ref} {product} {amount} {date} {shop}
placed:
  subject: "Your {shop} order {order_ref}"
  body: "Hello {name},\n\nThank you for your order {order_ref}: {product}, {amount}. We will e-mail you when it ships.\n\n{shop}"
shipped:
  subject: "Your order {order_ref} has shipped"
  body: "Hello {name},\n\n{product} is on its way. It is due by {date}.\n\n{shop}"
delayed:
  subject: "Your order {order_ref} is delayed"
  body: "Hello {name},\n\nSorry, {product} is delayed and is now expected by {date}. If it arrives late you may be entitled to compensation under our delivery policy.\n\n{shop}"
delivered:
  subject: "Your order {order_ref} was delivered"
  body: "Hello {name},\n\n{product} was delivered on {date}. If anything is wrong, reply to this e-mail or use Get help on the order.\n\n{shop}"
cancelled:
  subject: "Your order {order_ref} is cancelled"
  body: "Hello {name},\n\nYour order {order_ref} ({product}, {amount}) is cancelled. Any payment is refunded to the original method.\n\n{shop}"
returned:
  subject: "Your return for {order_ref} is approved"
  body: "Hello {name},\n\nWe have approved the return of {product}. The refund of {amount} follows our refund policy.\n\n{shop}"
return_refused:
  subject: "About your return for {order_ref}"
  body: "Hello {name},\n\nWe could not approve the return of {product}. Reply to this e-mail if you have questions.\n\n{shop}"
```

- [ ] **Step 2: Failing tests**

```python
"""Order e-mails: one per order and kind, only with an address and when switched on."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from database.models import OutboundEmail, User
from database.session import sync_session
from storefront.automation import advance_due_orders
from tests.fixtures.settings import use_settings
from tests.fixtures.shop import place_order, shopper

pytestmark = pytest.mark.db


def kinds() -> list[str]:
    with sync_session() as db:
        return [e.kind for e in db.scalars(select(OutboundEmail).order_by(OutboundEmail.created_at))]


async def test_placed_and_shipped_emails_once(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str]
) -> None:
    use_settings(orders={"delay_chance_pct": 0})
    order = await place_order(client, shopper(create_user, make_token), currency="PKR")
    now = datetime.now(UTC) + timedelta(hours=1)
    for _ in range(2):
        advance_due_orders(now)
        now += timedelta(minutes=5)
    assert kinds() == ["order_placed", "order_shipped"]
    with sync_session() as db:
        placed = db.scalars(select(OutboundEmail).where(OutboundEmail.kind == "order_placed")).one()
        assert order["order_ref"] in placed.subject and "Rs" in placed.body
        assert placed.to_address == "shopper@example.test" and placed.order_id is not None


async def test_switched_off_means_no_order_emails(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str]
) -> None:
    use_settings(orders={"emails": False})
    await place_order(client, shopper(create_user, make_token))
    assert kinds() == []
```

- [ ] **Step 3: Run** — Expected: FAIL (no e-mails queued).

- [ ] **Step 4: Implement `storefront/order_emails.py`**

```python
"""E-mails to customers when their order moves (through the outbox, like complaint replies)."""

from functools import lru_cache
from typing import Any

import yaml
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import app_settings
from database.models import Customer, Order, OutboundEmail
from email_channel.outbound import queue
from src.core.config import ROOT_DIR
from storefront.currency import CURRENCIES

EMAIL_KINDS = ("placed", "shipped", "delayed", "delivered", "cancelled", "returned", "return_refused")


@lru_cache
def _texts() -> dict[str, dict[str, str]]:
    with (ROOT_DIR / "config" / "order_emails.yaml").open(encoding="utf-8") as handle:
        data: dict[str, Any] = yaml.safe_load(handle)
    return data


def format_amount(order: Order) -> str:
    code = order.currency if order.currency in CURRENCIES else "USD"
    amount = order.amount_local if order.amount_local is not None else order.amount
    c = CURRENCIES[code]
    return f"{c.symbol} {amount:,.{c.decimals}f}"


def queue_order_email(
    db: Session | AsyncSession, order: Order, customer: Customer, kind: str
) -> OutboundEmail | None:
    settings = app_settings.runtime()
    if kind not in EMAIL_KINDS or not settings.orders.emails or not customer.email:
        return None
    if kind in (order.emails_sent or []):
        return None
    when = order.delivered_date if kind == "delivered" else (
        order.expected_delivery_date or order.committed_delivery_date)  # fmt: skip
    values = {
        "name": customer.full_name.split(" ")[0] if customer.full_name else "there",
        "order_ref": order.order_ref, "product": order.product_name,
        "amount": format_amount(order), "date": f"{when:%d %b %Y}" if when else "",
        "shop": settings.branding.shop_name,
    }  # fmt: skip
    text = _texts()[kind]
    order.emails_sent = [*(order.emails_sent or []), kind]
    return queue(
        db, complaint_id=None, order_id=order.id, to=customer.email, kind=f"order_{kind}",
        subject=text["subject"].format(**values), body=text["body"].format(**values),
        in_reply_to=None, references=[],
    )  # fmt: skip
```

`email_channel/outbound.queue`: add parameter `order_id: uuid.UUID | None = None` and pass
`order_id=order_id` to `OutboundEmail(...)`.
Checkout (`storefront/orders.checkout`): after the placed events, `queue_order_email(db, order, customer, "placed")` for each order.
Automation: after `delay(...)`: `queue_order_email(db, order, order.customer, "delayed")`; after `move(...)`: `queue_order_email(db, order, order.customer, order.stage)` (non-e-mail stages are ignored by the function).

- [ ] **Step 5: Run** `uv run pytest -q tests/integration/test_order_emails.py && uv run pytest -q` — Expected: PASS.

- [ ] **Step 6: Commit** `git commit -m "feat(orders): order e-mails through the outbox"`.

---

### Task 8: Customer order actions, history and receipts

**Files:**
- Create: `storefront/order_service.py`, `storefront/receipt.py`, `src/api/routes/orders.py`
- Modify: `src/main.py` (register router), `src/api/schemas.py` (`OrderEventOut`, `ReturnIn`)
- Test: `tests/integration/test_customer_orders.py`

**Interfaces:**
- Consumes: lifecycle (Task 3), `queue_order_email`, `format_amount` (Task 7), `storefront_config().returns.window_days`.
- Produces: `OrderNotFound`, `async load_order(db, ref) -> Order | None` (with customer and events loaded), `async own_order(db, user, ref) -> Order`, `async customer_cancel(db, user, ref) -> Order`, `async customer_return(db, user, ref, reason) -> Order`, `build_receipt(order, customer) -> bytes`; routes `POST /orders/{ref}/cancel`, `POST /orders/{ref}/return`, `GET /orders/{ref}/events`, `GET /orders/{ref}/receipt.pdf`.

- [ ] **Step 1: Failing tests**

```python
"""Customers cancel before shipping, return within 30 days, see history, get a receipt."""

from collections.abc import Callable
from datetime import date, timedelta

import httpx
import pytest
from sqlalchemy import update

from database.models import Order, Role, User
from database.session import sync_session
from tests.fixtures.shop import place_order, shopper

pytestmark = pytest.mark.db


def set_order(ref: str, **values: object) -> None:
    with sync_session() as db:
        db.execute(update(Order).where(Order.order_ref == ref).values(**values))


async def test_cancel_before_shipping_only(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str]
) -> None:
    me = shopper(create_user, make_token)
    ref = (await place_order(client, me))["order_ref"]
    done = await client.post(f"/api/v1/orders/{ref}/cancel", headers=me)
    assert done.status_code == 200 and done.json()["stage"] == "cancelled"
    other = (await place_order(client, me))["order_ref"]
    set_order(other, stage="shipped", status="shipped")
    assert (await client.post(f"/api/v1/orders/{other}/cancel", headers=me)).status_code == 409


async def test_return_within_the_window_with_a_reason(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str]
) -> None:
    me = shopper(create_user, make_token)
    ref = (await place_order(client, me))["order_ref"]
    set_order(ref, stage="delivered", status="delivered", delivered_date=date.today() - timedelta(days=5))
    short = await client.post(f"/api/v1/orders/{ref}/return", headers=me, json={"reason": "no"})
    assert short.status_code == 422
    ok = await client.post(f"/api/v1/orders/{ref}/return", headers=me,
                           json={"reason": "The left earcup rattles."})  # fmt: skip
    assert ok.status_code == 200 and ok.json()["stage"] == "return_requested"
    late = (await place_order(client, me))["order_ref"]
    set_order(late, stage="delivered", status="delivered", delivered_date=date.today() - timedelta(days=31))
    refused = await client.post(f"/api/v1/orders/{late}/return", headers=me,
                                json={"reason": "Changed my mind after a month."})  # fmt: skip
    assert refused.status_code == 409


async def test_other_customers_cannot_see_or_touch_an_order(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str]
) -> None:
    ref = (await place_order(client, shopper(create_user, make_token)))["order_ref"]
    stranger = shopper(create_user, make_token, email="stranger@example.test")
    for method, path in [("post", "cancel"), ("get", "events"), ("get", "receipt.pdf")]:
        response = await getattr(client, method)(f"/api/v1/orders/{ref}/{path}", headers=stranger)
        assert response.status_code == 404


async def test_history_and_receipt(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str],
    auth_headers: Callable[[Role], dict[str, str]],
) -> None:  # fmt: skip
    me = shopper(create_user, make_token)
    order = await place_order(client, me)
    events = (await client.get(f"/api/v1/orders/{order['order_ref']}/events", headers=me)).json()
    assert [e["stage"] for e in events] == ["placed"]
    pdf = await client.get(f"/api/v1/orders/{order['order_ref']}/receipt.pdf", headers=me)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert pdf.headers["content-type"] == "application/pdf"
    staff = await client.get(f"/api/v1/orders/{order['order_ref']}/receipt.pdf",
                             headers=auth_headers(Role.AGENT))  # fmt: skip
    assert staff.status_code == 200
```

- [ ] **Step 2: Run** — Expected: FAIL (404 on the new routes).

- [ ] **Step 3: `storefront/order_service.py`**

```python
"""Customer and staff actions on orders: load, check, move, e-mail."""

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import Customer, Order, User
from storefront.config import storefront_config
from storefront.lifecycle import LifecycleError, move
from storefront.order_emails import queue_order_email


class OrderNotFound(LookupError):
    pass


async def load_order(db: AsyncSession, ref: str) -> Order | None:
    return await db.scalar(
        select(Order)
        .options(selectinload(Order.customer), selectinload(Order.events))
        .where(Order.order_ref == ref.upper())
    )


async def own_order(db: AsyncSession, user: User, ref: str) -> Order:
    order = await load_order(db, ref)
    customer = await db.scalar(select(Customer).where(Customer.user_id == user.id))
    if order is None or customer is None or order.customer_id != customer.id:
        raise OrderNotFound(ref)
    return order


async def customer_cancel(db: AsyncSession, user: User, ref: str) -> Order:
    order = await own_order(db, user, ref)
    move(db, order, "cancelled", "customer", user_id=user.id, note="Cancelled by the customer")
    queue_order_email(db, order, order.customer, "cancelled")
    await db.commit()
    return order


async def customer_return(db: AsyncSession, user: User, ref: str, reason: str) -> Order:
    order = await own_order(db, user, ref)
    window = storefront_config().returns.window_days
    delivered = order.delivered_date
    if order.stage == "delivered" and delivered and (date.today() - delivered).days > window:
        raise LifecycleError(f"Returns are accepted within {window} days of delivery.", order.stage)
    move(db, order, "return_requested", "customer", user_id=user.id, note=reason,
         now=datetime.now(UTC))  # fmt: skip
    await db.commit()
    return order
```

- [ ] **Step 4: `storefront/receipt.py`**

```python
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
        ("Product", f"{order.product_name} × {order.quantity}"),
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
    pdf.drawString(20 * mm, 15 * mm, "VoltHaven Electronics is a fictional company created for a student project.")
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
```

- [ ] **Step 5: Routes `src/api/routes/orders.py`**

```python
"""Customer order actions, history and receipts (staff routes are added in Task 9)."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Order, User
from database.session import get_db
from security.dependencies import STAFF_ROLES, get_current_user
from src.api.schemas import OrderEventOut, ReturnIn, ShopOrderOut
from storefront.lifecycle import LifecycleError
from storefront.order_service import (
    OrderNotFound, customer_cancel, customer_return, load_order, own_order,
)  # fmt: skip
from storefront.receipt import build_receipt

router = APIRouter(tags=["orders"])


def _conflict(exc: LifecycleError) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, f"{exc} (the order is {exc.stage.replace('_', ' ')}).")


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
```

Schemas:

```python
class OrderEventOut(ORMModel):
    stage: str
    note: str | None
    actor: str
    created_at: datetime


class ReturnIn(BaseModel):
    reason: str = Field(min_length=10, max_length=500)
```

Register `orders.router` in `src/main.py` (import as `orders as order_routes`). Check that
`security.dependencies` exports `get_current_user` (it is used by `storefront.py`).

- [ ] **Step 6: Run** `uv run pytest -q tests/integration/test_customer_orders.py && uv run pytest -q` — Expected: PASS.

- [ ] **Step 7: Commit** `git commit -m "feat(orders): customer cancel, return, history and PDF receipts"`.

---

### Task 9: Staff orders API (replaces the Demo button)

**Files:**
- Modify: `storefront/order_service.py` (`staff_action`, `list_orders`), `src/api/routes/orders.py`, `src/api/schemas.py` (`StaffOrderOut`, `StaffOrderDetailOut`, `OrderActionIn`), `src/api/routes/storefront.py` (remove `simulate_delivery`), `storefront/orders.py` (remove `simulate`, `OUTCOMES`), `src/api/schemas.py` (remove `SimulateIn`)
- Modify tests: remove the simulate tests in `tests/unit/test_storefront_orders.py` and `tests/integration/test_storefront_api.py::test_delivery_outcomes_are_admin_only`
- Test: `tests/integration/test_staff_orders.py`

**Interfaces:**
- Consumes: lifecycle, e-mails, `load_order`.
- Produces: `async list_orders(db, *, stage=None, q=None, needs_action=False, limit=50, offset=0) -> list[Order]`, `async staff_action(db, user, ref, action, *, note=None, new_date=None, days_late=0) -> Order`; routes `GET /admin/orders`, `GET /admin/orders/{ref}`, `POST /admin/orders/{ref}/actions`.

- [ ] **Step 1: Failing tests**

```python
"""Staff move orders by hand, which pauses automation; returns are approved or refused."""

from collections.abc import Callable
from datetime import date, timedelta

import httpx
import pytest

from database.models import Role, User
from tests.fixtures.shop import place_order, shopper

pytestmark = pytest.mark.db


async def act(client: httpx.AsyncClient, headers: dict[str, str], ref: str, **body: object) -> httpx.Response:
    return await client.post(f"/api/v1/admin/orders/{ref}/actions", headers=headers, json=body)


async def test_staff_walk_an_order_to_a_late_delivery(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str],
    auth_headers: Callable[[Role], dict[str, str]],
) -> None:  # fmt: skip
    staff = auth_headers(Role.AGENT)
    ref = (await place_order(client, shopper(create_user, make_token)))["order_ref"]
    for _ in range(3):
        assert (await act(client, staff, ref, action="advance")).status_code == 200
    delayed = await act(client, staff, ref, action="delay", new_date=str(date.today() + timedelta(days=20)))
    assert delayed.status_code == 200
    done = (await act(client, staff, ref, action="advance", days_late=3)).json()
    assert done["stage"] == "delivered" and done["manual_hold"] is True
    detail = (await client.get(f"/api/v1/admin/orders/{ref}", headers=staff)).json()
    assert [e["stage"] for e in detail["events"]][-1] == "delivered"
    assert "3 business days late" in detail["events"][-1]["note"]


async def test_returns_and_illegal_actions(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str],
    auth_headers: Callable[[Role], dict[str, str]],
) -> None:  # fmt: skip
    staff, me = auth_headers(Role.AGENT), shopper(create_user, make_token)
    ref = (await place_order(client, me))["order_ref"]
    assert (await act(client, staff, ref, action="approve_return")).status_code == 409
    for _ in range(4):
        await act(client, staff, ref, action="advance")
    await client.post(f"/api/v1/orders/{ref}/return", headers=me, json={"reason": "The earcup rattles loudly."})
    listed = (await client.get("/api/v1/admin/orders?needs_action=true", headers=staff)).json()
    assert [o["order_ref"] for o in listed] == [ref]
    assert (await act(client, staff, ref, action="approve_return")).json()["stage"] == "returned"


async def test_customers_cannot_use_the_staff_api(
    client: httpx.AsyncClient, create_user: Callable[..., User], make_token: Callable[..., str]
) -> None:
    me = shopper(create_user, make_token)
    ref = (await place_order(client, me))["order_ref"]
    assert (await client.get("/api/v1/admin/orders", headers=me)).status_code == 403
    assert (await act(client, me, ref, action="advance")).status_code == 403
```

- [ ] **Step 2: Run** — Expected: FAIL (404).

- [ ] **Step 3: Service additions (`storefront/order_service.py`)**

```python
from sqlalchemy import or_

from storefront.lifecycle import FORWARD, delay, deliver_late

ACTIONS = ("advance", "delay", "lose", "cancel", "approve_return", "refuse_return", "resume_auto")


async def list_orders(
    db: AsyncSession, *, stage: str | None = None, q: str | None = None,
    needs_action: bool = False, limit: int = 50, offset: int = 0,
) -> list[Order]:  # fmt: skip
    stmt = (select(Order).join(Customer).options(selectinload(Order.customer))
            .where(Order.checkout_ref.is_not(None)))  # fmt: skip
    if stage:
        stmt = stmt.where(Order.stage == stage)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Order.order_ref.ilike(like), Order.product_name.ilike(like),
                              Customer.full_name.ilike(like), Customer.email.ilike(like)))  # fmt: skip
    if needs_action:
        stmt = stmt.where(or_(Order.stage == "return_requested",
                              (Order.expected_delivery_date.is_not(None)) & (Order.stage.in_(("shipped", "out_for_delivery")))))  # fmt: skip
    stmt = stmt.order_by(Order.created_at.desc()).limit(min(limit, 100)).offset(offset)
    return list((await db.scalars(stmt)).all())


async def staff_action(
    db: AsyncSession, user: User, ref: str, action: str, *,
    note: str | None = None, new_date: date | None = None, days_late: int = 0,
) -> Order:  # fmt: skip
    order = await load_order(db, ref)
    if order is None:
        raise OrderNotFound(ref)
    customer = order.customer
    if action == "resume_auto":
        order.manual_hold = False
        order.next_step_at = datetime.now(UTC)
    elif action == "delay":
        if new_date is None:
            raise LifecycleError("Give the new expected date.", order.stage)
        delay(db, order, new_date, "staff", user_id=user.id, note=note)
        queue_order_email(db, order, customer, "delayed")
    elif action == "advance" and order.stage == "out_for_delivery" and days_late > 0:
        deliver_late(db, order, days_late, user_id=user.id)
        queue_order_email(db, order, customer, "delivered")
    else:
        to = {"advance": FORWARD.get(order.stage, "?"), "lose": "lost", "cancel": "cancelled",
              "approve_return": "returned", "refuse_return": "return_refused"}[action]  # fmt: skip
        move(db, order, to, "staff", user_id=user.id, note=note)
        queue_order_email(db, order, customer, to)
    if action != "resume_auto":
        order.manual_hold = True
    await db.commit()
    return order
```

(`move` rejects `"?"` for stages with no forward step with a clear message.)

- [ ] **Step 4: Schemas and routes**

```python
class StaffOrderOut(ShopOrderOut):
    customer_name: str
    customer_email: str | None
    manual_hold: bool


class StaffOrderDetailOut(StaffOrderOut):
    events: list[OrderEventOut]
    complaint_refs: list[str]


class OrderActionIn(BaseModel):
    action: Literal["advance", "delay", "lose", "cancel", "approve_return", "refuse_return", "resume_auto"]
    note: str | None = Field(default=None, max_length=500)
    new_date: date | None = None
    days_late: int = Field(default=0, ge=0, le=30)
```

Routes appended to `src/api/routes/orders.py` (staff via `require_roles(*STAFF_ROLES)`):

```python
staff = require_roles(*STAFF_ROLES)


def _staff_out(order: Order) -> StaffOrderOut:
    return StaffOrderOut(
        **ShopOrderOut.model_validate(order).model_dump(),
        customer_name=order.customer.full_name,
        customer_email=order.customer.email,
        manual_hold=order.manual_hold,
    )


@router.get("/admin/orders", response_model=list[StaffOrderOut])
async def staff_orders(stage: str | None = None, q: str | None = None, needs_action: bool = False,
                       limit: int = 50, offset: int = 0, _: User = Depends(staff),
                       db: AsyncSession = Depends(get_db)) -> list[StaffOrderOut]:  # fmt: skip
    orders = await list_orders(db, stage=stage, q=q, needs_action=needs_action, limit=limit, offset=offset)
    return [_staff_out(o) for o in orders]


@router.get("/admin/orders/{ref}", response_model=StaffOrderDetailOut)
async def staff_order(ref: str, _: User = Depends(staff), db: AsyncSession = Depends(get_db)) -> StaffOrderDetailOut:
    order = await load_order(db, ref)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    refs = list(await db.scalars(select(Complaint.complaint_ref).where(Complaint.order_id == order.id)))
    base = _staff_out(order).model_dump()
    return StaffOrderDetailOut(**base, events=[OrderEventOut.model_validate(e) for e in order.events],
                               complaint_refs=refs)  # fmt: skip


@router.post("/admin/orders/{ref}/actions", response_model=StaffOrderOut)
async def staff_order_action(ref: str, payload: OrderActionIn, user: User = Depends(staff),
                             db: AsyncSession = Depends(get_db)) -> StaffOrderOut:  # fmt: skip
    try:
        order = await staff_action(db, user, ref, payload.action, note=payload.note,
                                   new_date=payload.new_date, days_late=payload.days_late)  # fmt: skip
    except OrderNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found") from exc
    except LifecycleError as exc:
        raise _conflict(exc) from exc
    await audit.record(db, "order.stage_changed", "order", order.order_ref, actor_user_id=user.id,
                       after={"action": payload.action, "stage": order.stage})  # fmt: skip
    await db.commit()
    return _staff_out(order)
```

Imports for the staff routes: `from sqlalchemy import select`, `from database import audit`,
`from database.models import Complaint`, `from security.dependencies import require_roles`, and the
new schemas and service functions.
Remove `simulate_delivery`, `SimulateIn`, `storefront.orders.simulate`/`OUTCOMES` and their tests.
Run `grep -rn "simulate" --include=*.py src storefront tests` — Expected: no matches.

- [ ] **Step 5: Run** `uv run pytest -q tests/integration/test_staff_orders.py && uv run pytest -q` — Expected: PASS.

- [ ] **Step 6: `make openapi`, commit** `git commit -m "feat(orders): staff orders API replaces the demo delivery button"`.

---

### Task 10: Web — currency

**Files:**
- Create: `web/src/lib/currency.tsx`, `web/src/components/shop/currency-switcher.tsx`
- Modify: `web/src/proxy.ts` (country cookie), `web/src/app/(shop)/layout.tsx` (provider), `web/src/components/shop/site-header.tsx` (switcher), `web/src/app/(shop)/checkout/page.tsx` (send currency), and replace `{formatMoney(x)}` with `<Price usd={x} />` in `product-detail.tsx`, `cart/page.tsx`, `order-summary.tsx`, `search-box.tsx`, `mini-cart.tsx`, `product-card.tsx`, `home/hero.tsx`, `home/feature-spotlight.tsx`; `order-list.tsx` uses `formatLocal(order)`.

**Interfaces:**
- Consumes: generated `currencyRatesOptions` (from `GET /currency`), `ShopOrderOut.currency/amount_local`.
- Produces: `CurrencyProvider`, `useCurrency(): { code, setCode, format(usd: number): string }`, `<Price usd className? />`, `formatLocal(order): string`.

- [ ] **Step 1: `web/src/lib/currency.tsx`**

```tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import { createContext, useContext, useMemo, useState } from "react";

import { currencyRatesOptions } from "@/lib/api/generated/@tanstack/react-query.gen";

const COOKIE = "currency";
const DIGITS: Record<string, number> = { USD: 2, PKR: 0, EUR: 2, GBP: 2, AED: 2 };
const SYMBOLS: Record<string, string> = { USD: "$", PKR: "Rs", EUR: "€", GBP: "£", AED: "AED" };

function readCookie(): string {
  if (typeof document === "undefined") return "USD";
  const match = document.cookie.match(/(?:^|; )currency=([A-Z]{3})/);
  return match?.[1] ?? "USD";
}

export function money(amount: number, code: string): string {
  const digits = DIGITS[code] ?? 2;
  const n = amount.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
  return code === "USD" ? `$${n}` : `${SYMBOLS[code] ?? code} ${n}`;
}

type Ctx = { code: string; setCode: (code: string) => void; format: (usd: number) => string; codes: string[] };
const CurrencyContext = createContext<Ctx | null>(null);

export function CurrencyProvider({ children }: { children: React.ReactNode }) {
  const [code, setState] = useState(readCookie);
  const rates = useQuery({ ...currencyRatesOptions(), staleTime: 60 * 60 * 1000 });
  const value = useMemo<Ctx>(() => {
    const table = rates.data?.rates ?? { USD: 1 };
    const active = table[code] ? code : "USD"; // no rate yet: show USD
    return {
      code: active,
      codes: Object.keys(table),
      setCode: (next) => {
        document.cookie = `${COOKIE}=${next}; path=/; max-age=31536000; samesite=lax`;
        setState(next);
      },
      format: (usd) => money(usd * (table[active] ?? 1), active),
    };
  }, [code, rates.data]);
  return <CurrencyContext.Provider value={value}>{children}</CurrencyContext.Provider>;
}

export function useCurrency(): Ctx {
  const ctx = useContext(CurrencyContext);
  return ctx ?? { code: "USD", codes: ["USD"], setCode: () => {}, format: (usd) => money(usd, "USD") };
}

export function Price({ usd, className }: { usd: number; className?: string }) {
  return <span className={className}>{useCurrency().format(usd)}</span>;
}

/** What the customer paid, in the currency they saw at checkout. */
export function formatLocal(order: { amount: number; currency: string; amount_local?: number | null }): string {
  return money(order.amount_local ?? order.amount, order.amount_local == null ? "USD" : order.currency);
}
```

- [ ] **Step 2: Switcher, provider, proxy, checkout**

`web/src/components/shop/currency-switcher.tsx`:

```tsx
"use client";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useCurrency } from "@/lib/currency";

export function CurrencySwitcher() {
  const { code, codes, setCode } = useCurrency();
  return (
    <Select value={code} onValueChange={setCode}>
      <SelectTrigger size="sm" className="w-[5.5rem]" aria-label="Currency">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {codes.map((c) => (
          <SelectItem key={c} value={c}>{c}</SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
```

`(shop)/layout.tsx`: wrap the layout's children in `<CurrencyProvider>…</CurrencyProvider>`.
`site-header.tsx`: render `<CurrencySwitcher />` next to the cart button.
`proxy.ts`: replace the middleware body with:

```ts
export default clerkMiddleware(async (auth, request) => {
  if (!isPublicRoute(request)) {
    await auth.protect();
  }
  if (!request.cookies.get("currency")) {
    // Vercel adds the visitor's country; the API never sees it, so the default is set here.
    const country = request.headers.get("x-vercel-ip-country");
    const response = NextResponse.next();
    response.cookies.set("currency", country === "PK" ? "PKR" : "USD", {
      path: "/", maxAge: 60 * 60 * 24 * 365, sameSite: "lax",
    });
    return response;
  }
});
```

(`import { NextResponse } from "next/server";`)
Checkout page: include `currency: useCurrency().code` in the `placeOrderMutation` body.
Replace every shop `{formatMoney(expr)}` with `<Price usd={expr} />` in the listed files
(keep `formatMoney` in `products-manager.tsx`, which is staff and USD); in `order-list.tsx`
replace `{formatMoney(o.amount)}` with `{formatLocal(o)}`.

- [ ] **Step 3: Verify**

Run `make openapi && pnpm --dir web exec prettier --write src && pnpm --dir web lint && pnpm --dir web typecheck && pnpm --dir web build` — Expected: clean.
Browser: with the local API running, set cookie `currency=PKR` → shop prices show "Rs …"; switcher to USD shows "$…".

- [ ] **Step 4: Commit** `git commit -m "feat(web): prices in the visitor's currency with a switcher"`.

---

### Task 11: Web — My orders tracker, history and actions; Settings Orders tab

**Files:**
- Create: `web/src/components/shop/order-tracker.tsx`
- Modify: `web/src/components/shop/order-list.tsx` (use the tracker; remove `DeliveryControls`), `web/src/components/complaints/complaint-view.tsx` (remove `DeliveryControls`), delete `web/src/components/shop/delivery-controls.tsx`, `web/src/components/settings/settings-manager.tsx` (Orders tab)

**Interfaces:**
- Consumes: generated `cancelOrderMutation`, `requestReturnMutation`, `orderEventsOptions`, `orderReceipt` (sdk), `ShopOrderOut`, `formatLocal`.
- Produces: `<OrderTracker order={ShopOrderOut} />`.

- [ ] **Step 1: `order-tracker.tsx`**

```tsx
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { orderReceipt } from "@/lib/api/generated/sdk.gen";
import {
  cancelOrderMutation,
  myShopOrdersQueryKey,
  orderEventsOptions,
  requestReturnMutation,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import type { ShopOrderOut } from "@/lib/api/generated/types.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { saveBlob } from "@/lib/download";
import { formatDate, formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

const STEPS = ["placed", "packed", "shipped", "out_for_delivery", "delivered"] as const;
const LABEL: Record<string, string> = {
  placed: "Placed", packed: "Packed", shipped: "Shipped", out_for_delivery: "Out for delivery",
  delivered: "Delivered", lost: "Lost in transit", cancelled: "Cancelled",
  return_requested: "Return requested", return_refused: "Return refused", returned: "Returned",
  delayed: "Delayed",
};
const RETURN_DAYS = 30;

export function OrderTracker({ order: o }: { order: ShopOrderOut }) {
  const queryClient = useQueryClient();
  const [returning, setReturning] = useState(false);
  const [reason, setReason] = useState("");
  const history = useQuery(orderEventsOptions({ path: { ref: o.order_ref } }));
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: myShopOrdersQueryKey() });
    history.refetch();
  };
  const onError = (err: unknown) => toast.error(apiErrorMessage(err));
  const cancel = useMutation({ ...cancelOrderMutation(), onSuccess: () => { toast.success("Order cancelled"); refresh(); }, onError });
  const ret = useMutation({ ...requestReturnMutation(), onSuccess: () => { toast.success("Return requested"); setReturning(false); refresh(); }, onError });

  const reached = STEPS.indexOf(o.stage as (typeof STEPS)[number]);
  const endLabel = reached === -1 && o.stage !== "placed" ? LABEL[o.stage] : null;
  const delivered = o.delivered_date ? new Date(o.delivered_date) : null;
  const canReturn = o.stage === "delivered" && delivered !== null &&
    (Date.now() - delivered.getTime()) / 86_400_000 <= RETURN_DAYS;

  async function receipt() {
    try {
      const { data } = await orderReceipt({ path: { ref: o.order_ref }, parseAs: "blob", throwOnError: true });
      saveBlob(data as Blob, `receipt-${o.order_ref}.pdf`);
    } catch (err) {
      onError(err);
    }
  }

  return (
    <div className="mt-3 space-y-3">
      <ol className="flex flex-wrap items-center gap-2 text-[11px]" aria-label="Order progress">
        {STEPS.map((step, i) => (
          <li key={step} className="flex items-center gap-2">
            <span className={cn("rounded-full px-2 py-0.5", i <= reached ? "bg-brand text-brand-foreground" : "bg-muted text-muted-foreground")}>
              {LABEL[step]}
            </span>
            {i < STEPS.length - 1 ? <span className="h-px w-4 bg-border" /> : null}
          </li>
        ))}
        {endLabel ? <li className="rounded-full bg-destructive/10 px-2 py-0.5 text-destructive">{endLabel}</li> : null}
      </ol>
      <p className="text-xs text-muted-foreground">
        Promised by {formatDate(o.committed_delivery_date)}
        {o.expected_delivery_date ? ` · now expected ${formatDate(o.expected_delivery_date)}` : ""}
      </p>
      {history.data?.length ? (
        <ul className="space-y-1 border-l pl-3 text-xs">
          {history.data.map((e) => (
            <li key={`${e.stage}-${e.created_at}`}>
              <span className="font-medium">{LABEL[e.stage] ?? e.stage}</span>
              <span className="text-muted-foreground"> · {formatDateTime(e.created_at)}{e.note ? ` · ${e.note}` : ""}</span>
            </li>
          ))}
        </ul>
      ) : null}
      <div className="flex flex-wrap gap-2">
        {o.stage === "placed" || o.stage === "packed" ? (
          <Button size="sm" variant="outline" disabled={cancel.isPending} onClick={() => cancel.mutate({ path: { ref: o.order_ref } })}>
            Cancel order
          </Button>
        ) : null}
        {canReturn ? (
          <Button size="sm" variant="outline" onClick={() => setReturning((v) => !v)}>Request a return</Button>
        ) : null}
        <Button size="sm" variant="ghost" onClick={receipt}>Receipt</Button>
      </div>
      {returning ? (
        <div className="space-y-2">
          <Textarea value={reason} maxLength={500} placeholder="What is wrong with it? (at least 10 characters)" onChange={(e) => setReason(e.target.value)} />
          <Button size="sm" disabled={reason.trim().length < 10 || ret.isPending}
            onClick={() => ret.mutate({ path: { ref: o.order_ref }, body: { reason: reason.trim() } })}>
            Send return request
          </Button>
        </div>
      ) : null}
    </div>
  );
}
```

(Check the generated names after `make openapi`: route functions `cancel_order`, `request_return`, `order_events`, `order_receipt`, `my_shop_orders` → `cancelOrderMutation`, `requestReturnMutation`, `orderEventsOptions`, `orderReceipt`, `myShopOrdersQueryKey`.)

- [ ] **Step 2: Use it; remove the Demo button**

In `order-list.tsx` replace the old `Timeline` and `statusLine` usage with `<OrderTracker order={o} />`
and delete the `DeliveryControls` import and element; in `complaint-view.tsx` delete the
`DeliveryControls` import and element; `git rm web/src/components/shop/delivery-controls.tsx`.

- [ ] **Step 3: Settings Orders tab** (`settings-manager.tsx`, after the Operations tab)

```tsx
        <TabsTrigger value="orders">Orders</TabsTrigger>
```

```tsx
      <TabsContent value="orders" className="space-y-6 rounded-xl border p-6">
        <Field label="Advance orders automatically" help="Off: orders move only when staff move them.">
          <Switch checked={form.orders.auto_advance} onCheckedChange={(v) => set("orders", { auto_advance: v })} />
        </Field>
        <Field label="Minutes per step" help="1 to 1440. With 2, a demo order is delivered in about 10 minutes.">
          <NumberInput value={form.orders.step_minutes} min={1} max={1440} onChange={(v) => set("orders", { step_minutes: v })} />
        </Field>
        <Field label="Chance of a delay (%)" help="0 to 100. A delayed order is expected 2–5 business days after the promise.">
          <NumberInput value={form.orders.delay_chance_pct} min={0} max={100} onChange={(v) => set("orders", { delay_chance_pct: v })} />
        </Field>
        <Field label="Chance of loss (%)" help="0 to 20.">
          <NumberInput value={form.orders.lost_chance_pct} min={0} max={20} onChange={(v) => set("orders", { lost_chance_pct: v })} />
        </Field>
        <Field label="Send order e-mails" help="Placed, shipped, delayed, delivered, cancelled and return decisions.">
          <Switch checked={form.orders.emails} onCheckedChange={(v) => set("orders", { emails: v })} />
        </Field>
        <Field label="Fallback PKR rate" help="Used only until the first exchange-rate refresh succeeds.">
          <NumberInput value={form.orders.fallback_pkr_rate} min={1} max={10000} onChange={(v) => set("orders", { fallback_pkr_rate: v })} />
        </Field>
        {footer}
      </TabsContent>
```

Also add `orders: s.settings.orders` in `toForm`.

- [ ] **Step 4: Verify** `pnpm --dir web exec prettier --write src && pnpm --dir web lint && pnpm --dir web typecheck && pnpm --dir web build` — Expected: clean. Browser check of My orders with a local order (tracker, history, cancel).

- [ ] **Step 5: Commit** `git commit -m "feat(web): order tracker, history, cancel, return and receipt; Settings orders tab"`.

---

### Task 12: Web — staff Orders page

**Files:**
- Create: `web/src/app/(app)/fulfilment/page.tsx`, `web/src/components/fulfilment/orders-manager.tsx`
- Modify: `web/src/components/app-sidebar.tsx` (nav item "Orders", `/fulfilment`, `Truck` icon, staff roles, under Complaints)

**Interfaces:**
- Consumes: generated `staffOrdersOptions`, `staffOrderOptions`, `staffOrderActionMutation`, `orderReceipt`; `formatLocal`, `money`.

- [ ] **Step 1: Page**

```tsx
import { redirect } from "next/navigation";

import { OrdersManager } from "@/components/fulfilment/orders-manager";
import { PageHeader } from "@/components/page-header";
import { getCurrentUser } from "@/lib/api/server";
import { isStaff } from "@/lib/roles";

export const metadata = { title: "Orders" };

export default async function FulfilmentPage() {
  const result = await getCurrentUser();
  if (result.status !== "ok" || !isStaff(result.user.role)) redirect("/dashboard");
  return (
    <>
      <PageHeader title="Orders" description="Shop orders and their progress. Moving an order by hand pauses its automatic progress until you resume it." />
      <OrdersManager />
    </>
  );
}
```

- [ ] **Step 2: `orders-manager.tsx`**

```tsx
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { orderReceipt } from "@/lib/api/generated/sdk.gen";
import {
  staffOrderActionMutation,
  staffOrderOptions,
  staffOrdersOptions,
} from "@/lib/api/generated/@tanstack/react-query.gen";
import { apiErrorMessage } from "@/lib/api/errors";
import { formatLocal, money } from "@/lib/currency";
import { saveBlob } from "@/lib/download";
import { formatDate, formatDateTime } from "@/lib/format";

const STAGES = ["placed", "packed", "shipped", "out_for_delivery", "delivered", "lost", "cancelled", "return_requested", "return_refused", "returned"];
const label = (s: string) => s.replaceAll("_", " ");

type Action = "advance" | "delay" | "lose" | "cancel" | "approve_return" | "refuse_return" | "resume_auto";
const ACTIONS: Record<string, { action: Action; text: string }[]> = {
  placed: [{ action: "advance", text: "Mark packed" }, { action: "cancel", text: "Cancel" }],
  packed: [{ action: "advance", text: "Mark shipped" }, { action: "cancel", text: "Cancel" }],
  shipped: [{ action: "advance", text: "Out for delivery" }, { action: "delay", text: "Delay" }, { action: "lose", text: "Mark lost" }],
  out_for_delivery: [{ action: "advance", text: "Mark delivered" }, { action: "delay", text: "Delay" }, { action: "lose", text: "Mark lost" }],
  return_requested: [{ action: "approve_return", text: "Approve return" }, { action: "refuse_return", text: "Refuse return" }],
};

export function OrdersManager() {
  const queryClient = useQueryClient();
  const [stage, setStage] = useState("all");
  const [q, setQ] = useState("");
  const [needsAction, setNeedsAction] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const [newDate, setNewDate] = useState("");
  const [daysLate, setDaysLate] = useState(0);
  const list = useQuery(staffOrdersOptions({ query: { stage: stage === "all" ? undefined : stage, q: q || undefined, needs_action: needsAction } }));
  const detail = useQuery({ ...staffOrderOptions({ path: { ref: open ?? "" } }), enabled: Boolean(open) });
  const act = useMutation({
    ...staffOrderActionMutation(),
    onSuccess: () => { toast.success("Order updated"); queryClient.invalidateQueries(); },
    onError: (err) => toast.error(apiErrorMessage(err)),
  });
  const run = (action: Action) =>
    open && act.mutate({ path: { ref: open }, body: { action, new_date: action === "delay" ? newDate || null : null, days_late: action === "advance" ? daysLate : 0 } });

  async function receipt(ref: string) {
    try {
      const { data } = await orderReceipt({ path: { ref }, parseAs: "blob", throwOnError: true });
      saveBlob(data as Blob, `receipt-${ref}.pdf`);
    } catch (err) {
      toast.error(apiErrorMessage(err));
    }
  }

  const o = detail.data;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Input className="max-w-xs" placeholder="Search order, customer or product" value={q} onChange={(e) => setQ(e.target.value)} />
        <Select value={stage} onValueChange={setStage}>
          <SelectTrigger className="w-48"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All stages</SelectItem>
            {STAGES.map((s) => <SelectItem key={s} value={s}>{label(s)}</SelectItem>)}
          </SelectContent>
        </Select>
        <label className="flex items-center gap-2 text-sm"><Switch checked={needsAction} onCheckedChange={setNeedsAction} /> Needs action</label>
      </div>
      {list.isPending ? <Skeleton className="h-64 w-full" /> : list.isError ? (
        <p className="text-sm text-destructive">{apiErrorMessage(list.error)}</p>
      ) : (
        <div className="rounded-xl border">
          <Table>
            <TableHeader><TableRow>
              <TableHead>Order</TableHead><TableHead>Customer</TableHead><TableHead>Product</TableHead>
              <TableHead>Stage</TableHead><TableHead>Promised</TableHead><TableHead className="text-right">Paid</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {list.data.map((r) => (
                <TableRow key={r.order_ref} className="cursor-pointer" onClick={() => setOpen(r.order_ref)}>
                  <TableCell className="font-mono text-xs">{r.order_ref}</TableCell>
                  <TableCell>{r.customer_name}</TableCell>
                  <TableCell>{r.product_name}</TableCell>
                  <TableCell>
                    <Badge variant={r.stage === "return_requested" || r.expected_delivery_date ? "destructive" : "secondary"}>{label(r.stage)}</Badge>
                    {r.manual_hold ? <span className="ml-1 text-xs text-muted-foreground">(manual)</span> : null}
                  </TableCell>
                  <TableCell>{formatDate(r.committed_delivery_date)}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatLocal(r)}</TableCell>
                </TableRow>
              ))}
              {list.data.length === 0 ? <TableRow><TableCell colSpan={6} className="text-center text-sm text-muted-foreground">No orders.</TableCell></TableRow> : null}
            </TableBody>
          </Table>
        </div>
      )}
      <Sheet open={Boolean(open)} onOpenChange={(v) => !v && setOpen(null)}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
          <SheetHeader><SheetTitle>{open}</SheetTitle></SheetHeader>
          {!o ? <Skeleton className="m-4 h-64" /> : (
            <div className="space-y-5 p-4 text-sm">
              <div className="grid grid-cols-2 gap-2">
                <span className="text-muted-foreground">Customer</span><span>{o.customer_name} · {o.customer_email ?? "no e-mail"}</span>
                <span className="text-muted-foreground">Product</span><span>{o.product_name} × {o.quantity}</span>
                <span className="text-muted-foreground">Paid</span><span>{formatLocal(o)} (USD reference {money(o.amount, "USD")})</span>
                <span className="text-muted-foreground">Promised</span><span>{formatDate(o.committed_delivery_date)}{o.expected_delivery_date ? `, now expected ${formatDate(o.expected_delivery_date)}` : ""}</span>
                <span className="text-muted-foreground">Complaints</span><span>{o.complaint_refs.length ? o.complaint_refs.join(", ") : "—"}</span>
              </div>
              <ul className="space-y-1 border-l pl-3 text-xs">
                {o.events.map((e) => (
                  <li key={`${e.stage}-${e.created_at}`}><span className="font-medium">{label(e.stage)}</span>
                    <span className="text-muted-foreground"> · {e.actor} · {formatDateTime(e.created_at)}{e.note ? ` · ${e.note}` : ""}</span></li>
                ))}
              </ul>
              <div className="space-y-2">
                {o.stage === "out_for_delivery" ? (
                  <label className="flex items-center gap-2 text-xs">Deliver
                    <Input type="number" min={0} max={30} className="w-16" value={daysLate} onChange={(e) => setDaysLate(Number(e.target.value))} />
                    business days late (demo)</label>
                ) : null}
                {o.stage === "shipped" || o.stage === "out_for_delivery" ? (
                  <label className="flex items-center gap-2 text-xs">New expected date
                    <Input type="date" className="w-40" value={newDate} onChange={(e) => setNewDate(e.target.value)} /></label>
                ) : null}
                <div className="flex flex-wrap gap-2">
                  {(ACTIONS[o.stage] ?? []).map((a) => (
                    <Button key={a.action} size="sm" variant={a.action === "lose" || a.action === "cancel" ? "outline" : "default"}
                      disabled={act.isPending || (a.action === "delay" && !newDate)} onClick={() => run(a.action)}>{a.text}</Button>
                  ))}
                  {o.manual_hold ? <Button size="sm" variant="ghost" onClick={() => run("resume_auto")}>Resume automatic progress</Button> : null}
                  <Button size="sm" variant="ghost" onClick={() => receipt(o.order_ref)}>Receipt</Button>
                </div>
              </div>
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}
```

(Check generated names after `make openapi`: `staff_orders`, `staff_order`, `staff_order_action` → `staffOrdersOptions`, `staffOrderOptions`, `staffOrderActionMutation`.)

- [ ] **Step 3: Sidebar** — in the Complaints group add
`{ title: "Orders", href: "/fulfilment", icon: Truck, roles: STAFF },` and import `Truck`.

- [ ] **Step 4: Verify** — prettier, lint, typecheck, build clean; `/fulfilment` in the build output.

- [ ] **Step 5: Commit** `git commit -m "feat(web): staff Orders page"`.

---

### Task 13: Documentation and final verification

**Files:** `documentation/user_guide.md` (section "Orders" for customers and staff; Settings → Orders tab), `documentation/deployment.md` (migration; exchange rates need outbound HTTPS to open.er-api.com), `README.md`, `documentation/project_report.md` (functional requirements row), `AI_USAGE.md` (entry), test counts.

- [ ] **Step 1: Docs** — write the sections above; update test counts from `uv run pytest -q | tail -1`.
- [ ] **Step 2: Verify** — `uv run ruff check . && uv run ruff format --check <python paths> && uv run mypy . && uv run pytest -q`; `pnpm --dir web lint && pnpm --dir web typecheck && pnpm --dir web build` — all clean.
- [ ] **Step 3: Commit** `git commit -m "docs: orders lifecycle and local currency"`.
