# Orders lifecycle, order e-mails, returns, receipts and local currency: design

Date: 2026-09-28. Status: approved in conversation, awaiting spec review.

## Goal

Shop orders behave like real orders: they move through a courier-like lifecycle on their own
(and by staff action), keep a full history, send e-mails, can be cancelled or returned, have a
receipt, and are shown in the visitor's local currency (PKR in Pakistan). Complaints, the AI
and the rules keep working on real order data.

## Decisions (from the conversation)

- Orders advance **automatically and manually** (option "Auto + manual").
- Currency is **local display**: prices stay stored in USD; visitors see their currency.
- Extras included: **order e-mails**, **cancel and return**, **receipts**. Stock levels are out.
- The admin "Demo" delivery button is replaced by the staff Orders page actions.

## 1. Stages, status and history

`Order` gets a fine-grained `stage`; the existing coarse `status` stays and is derived from it,
because the rule-matrix vocabulary (`complaint_rules/facts.py`: "processing, shipped,
delivered, lost or returned"), the chat and the AI read `status`.

| Stage | Status (derived) | Notes |
|---|---|---|
| `placed` | processing | set at checkout |
| `packed` | processing | |
| `shipped` | shipped | |
| `out_for_delivery` | shipped | |
| `delivered` | delivered | sets `delivered_date` |
| `lost` | lost | |
| `cancelled` | cancelled | only from placed or packed |
| `return_requested` | delivered | customer, within the return window |
| `return_refused` | delivered | staff, with a reason |
| `returned` | returned | staff approves the return |

- Allowed moves (anything else is refused with 409):
  placed → packed → shipped → out_for_delivery → delivered;
  placed/packed → cancelled; shipped/out_for_delivery → lost;
  delivered → return_requested (customer, ≤ `returns.window_days` = 30 days after delivery);
  return_requested → returned | return_refused.
- **Delayed** is not a stage: while shipped/out_for_delivery, staff or the automation can set a
  new `committed_delivery_date` (the promise moves; an event "Delayed: new date …" is recorded).
- The coarse vocabulary gains `cancelled` (added to `complaint_rules/facts.py`).
- New table `order_events`: `id`, `order_id` (FK, index), `stage`, `note`, `actor`
  (`system` | `staff` | `customer`), `actor_user_id` (nullable), `created_at`. Every move and
  every delay writes one event; staff moves are also audited (`order.stage_changed`).
- Only shop orders (`checkout_ref` not null) have stages that move; the dataset's historic
  orders are migrated to a stage mirroring their current `status` (processing → placed,
  shipped → shipped, delivered → delivered, lost → lost, returned → returned) and never advance.

`storefront/lifecycle.py` owns this: `move(db, order, to, actor, *, user=None, note=None, now)`
and `delay(db, order, new_date, actor, *, user=None, note=None, now)`; both validate, update
`stage`, `status`, dates, write the event and queue the order e-mail (section 4).

## 2. Automatic progress

- A new job `order-progress` in `app_settings.jobs.JOBS` (runs on the existing tick).
- New Settings group `orders` (tab **Orders**):

| Field | Limits | Default |
|---|---|---|
| `auto_advance` | bool | true |
| `step_minutes` | 1–1440 | 2 |
| `delay_chance_pct` | 0–100 | 10 |
| `lost_chance_pct` | 0–20 | 0 |
| `emails` | bool | true |
| `fallback_pkr_rate` | 1–10000 | 280 |

- Each shop order has `next_step_at` (set at checkout to `now + step_minutes`) and
  `manual_hold` (bool). The job takes up to 50 orders with `next_step_at <= now`, stage in
  placed/packed/shipped/out_for_delivery, `manual_hold = false`, and moves each one step; the
  next `next_step_at` is `now + step_minutes`; delivered/lost/cancelled clear it.
- On leaving `shipped`, a seeded random draw decides: lost (`lost_chance_pct`, only from
  out_for_delivery), delayed (`delay_chance_pct`: new promised date 2–5 business days later,
  once per order), else normal. The random source is injectable for tests.
- Any staff action sets `manual_hold = true`; the staff "Resume automatic progress" action
  clears it. Customer actions (cancel, return request) do not change automation.

## 3. Staff Orders page (`/fulfilment`, titled "Orders", staff roles)

- `GET /api/v1/admin/orders` (staff): shop orders, newest first, filters `stage`, `q` (order
  ref, customer name or e-mail, product), `needs_action` (return_requested, or delayed and not
  delivered), paging (limit 50, offset).
- `GET /api/v1/admin/orders/{ref}` (staff): order, customer, amounts, events, related
  complaint refs.
- `POST /api/v1/admin/orders/{ref}/actions` (staff) body `{action, note?, new_date?}` with
  `action` ∈ `advance`, `delay`, `lose`, `cancel`, `approve_return`, `refuse_return`,
  `resume_auto`. Validation errors 422, illegal moves 409.
- Web: table with stage badges and filters; a side panel with the timeline, amounts (USD and
  paid currency), customer, complaints, and the action buttons that are legal for the stage;
  receipt download.
- Sidebar item "Orders" under Complaints. The Demo button (`delivery-controls.tsx`) and
  `POST /orders/{ref}/simulate` are removed; `storefront/orders.simulate` goes with them.

## 4. Order e-mails

- Stages placed, shipped, delivered, cancelled, returned, return_refused and a delay each queue
  one e-mail through the existing outbox (`OutboundEmail`, `complaint_id` null, new `order_id`
  column, `kind` = `order_<stage>` or `order_delayed`), only if `orders.emails` is on and the
  customer has an e-mail. Texts live in `config/order_emails.yaml` with the order ref, product,
  local amount and dates; signed with the branding shop name.
- At most one e-mail per order and kind (a unique check before queueing).
- Sent by the existing flush with the configured sender (Brevo on Railway).

## 5. Customer side

- My orders (`/orders`): each order shows a progress tracker (placed → delivered, or the
  lost/cancelled/returned end), the promised date (with "was …" when delayed), the history, and
  buttons: **Cancel order** (placed/packed), **Request a return** (delivered, within 30 days;
  reason required, 10–500 characters), **Receipt**.
- `POST /api/v1/orders/{ref}/cancel` and `POST /api/v1/orders/{ref}/return` (the order's own
  customer only; others 404). `GET /api/v1/orders/{ref}/events` for the history.
- Get help on an order (chat) keeps working; the chat sees the coarse status.

## 6. Currency

- Supported: USD, PKR, EUR, GBP, AED (`storefront/currency.py`: code, symbol, decimals — PKR 0,
  others 2).
- Table `fx_rates(currency pk, rate numeric(14,6), fetched_at)`; job `fx-refresh` (every 12 h
  on the tick) fetches `https://open.er-api.com/v6/latest/USD` (httpx, 10 s timeout) and
  stores the five rates. On failure the last stored rates stay; with none stored, PKR uses
  `orders.fallback_pkr_rate` and the others are unavailable (shown in USD).
- `GET /api/v1/currency` (public): `{rates: {code: rate}, fetched_at, default}` where
  `default` comes from the request header `x-vercel-ip-country` (`PK` → PKR, else USD).
- Web: a `CurrencyProvider` reads `/currency` once; the visitor's choice is kept in the
  `currency` cookie (switcher in the shop header). All shop prices go through
  `formatPrice(usd, currency)`; PKR shows "Rs 12,500", others with 2 decimals.
- Checkout body gains `currency`; the server stores on each order `currency`, `fx_rate`
  (from `fx_rates`/fallback at that moment) and `amount_local` (rounded to the currency's
  decimals). `amount` stays USD. Staff screens show both; customer screens, e-mails and
  receipts show the local amount (and "USD x.xx" as reference on the receipt).
- Policies, rules, analytics and the AI keep using USD `amount`.

## 7. Receipts

- `GET /api/v1/orders/{ref}/receipt.pdf` (own customer or staff): ReportLab PDF — shop name and
  logo (branding), receipt number = order ref, date, customer, product, quantity, shipping
  method, amount in the paid currency, USD reference and rate, transaction ref, status.

## 8. Error handling

- Illegal moves → 409 with the current stage; customer acting on another's order → 404.
- The automation logs and skips an order that fails; the batch continues.
- Exchange-rate fetch failure never blocks checkout (last rates / fallback).
- E-mails failing follow the existing outbox retries.

## 9. Tests

- Lifecycle: every allowed move; refused moves; status mapping; events written; delay moves the
  promise once; dataset orders never move.
- Automation: only due, not-held shop orders move; batch limit; seeded delay and loss; hold and
  resume; failure of one order does not stop the batch.
- Staff API: roles, filters, each action, 409/422.
- Customer API: cancel before shipping only; return within 30 days only, reason required;
  another customer's order 404; history.
- E-mails: one per order and kind; off switch; no e-mail address → nothing.
- Currency: country default, rates stored, fetch failure keeps rates, fallback PKR, checkout
  stores currency/rate/local amount with correct rounding.
- Receipt: PDF bytes, content includes ref and amounts, access rules.
- Regression: existing complaint, chat and dataset tests pass; the rule fact vocabulary
  includes `cancelled`.

## Out of scope

- Stock levels; real payments; refunds to cards; changing policy amounts to PKR; stages for
  dataset orders.
