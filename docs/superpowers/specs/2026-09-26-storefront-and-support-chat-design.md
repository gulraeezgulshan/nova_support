# Storefront and support chat: design

Date: 2026-09-26 · Status: approved in conversation, awaiting spec review

## 1. Purpose

Make the SupportNova demo realistic end to end: a customer shops at VoltHaven, places an
order, runs into a problem and complains **through a chat assistant**, which gathers the
details, files the complaint through the existing pipelines and replies with the validated
answer. This is beyond the SRS minimum (the SRS mentions chat only as a background complaint
channel) and must not weaken any SRS guarantee.

**Success criteria**

- A signed-in customer can browse products, check out without payment and see their orders.
- From an order (or anywhere in the shop) the customer can open a chat, describe a problem,
  confirm a summary and receive a complaint reference.
- The chat shows the Pipeline 1 reply automatically when Pipeline 2's verdict is *verified*
  or *corrected*, and otherwise a holding message followed by the reviewer-approved reply.
- The AI in the chat never decides or promises a remedy; every complaint still goes through
  intake, Pipeline 1 and Pipeline 2 unchanged.
- Works with both GenAI providers (`GENAI_PROVIDER=anthropic|openai`).

**Decisions taken**

| Question | Decision |
|---|---|
| Shop depth | Demo shop: catalogue, product pages, cart, checkout without payment, order tracking |
| Chat behaviour | Guided conversational intake, then confirm, then submit |
| When replies are sent automatically | When Python's verdict is verified or corrected; otherwise a human approves first |
| Structure | One web app (shop section + existing staff console), polling for chat updates |

## 2. Storefront

### 2.1 Data

- **`products`** (new): `sku` (unique, e.g. `VH-PHN-NX5`), `name`, `product_line` (the
  existing product-category codes: SMARTPHONE, LAPTOP, TABLET, AUDIO, WEARABLE, NETWORKING,
  SMART_HOME, ACCESSORY), `price` (Numeric 10,2), `description`, `specs` (JSONB list of
  strings), `is_active`. Seeded idempotently from `config/catalogue.yaml` (~16 products,
  reusing product names already in the dataset: Nova X5, AeroBook 14, Pulse Buds Pro,
  VoltCharge 65W, …).
- **`orders`** (existing) gains `product_id` (nullable FK), `quantity` (default 1) and
  `checkout_ref` (nullable, e.g. `CHK-000012`, shared by the lines of one checkout). `amount`
  stays the line total (price × quantity), so complaint facts are unchanged.
- One `Order` row per cart line. Committed delivery date = order date + 3 business days
  (standard) or 1 (express); status `processing`.

### 2.2 API (`storefront/` module, routes in `src/api/routes/storefront.py`)

| Endpoint | Access | Behaviour |
|---|---|---|
| `GET /products` | public | Active products, optional `product_line` filter |
| `GET /products/{sku}` | public | One product |
| `POST /checkout` | signed in | Body: lines `[{sku, quantity}]`, `shipping_method`; prices always from the server; creates the customer profile if needed; returns the created orders |
| `GET /orders` | signed in | The customer's orders, newest first, with status timeline |
| `POST /orders/{order_ref}/simulate` | admin | Demo delivery outcome: `on_time`, `late` (with `days`), `lost`, `damaged` |

Validation: 1–10 lines, quantity 1–5, known active SKUs, shipping `standard|express`.
The existing `GET /customers/me/orders` stays for the complaint form.

### 2.3 Pages (Next.js)

- `/` home (featured products, product lines); the current landing page moves to `/about`.
- `/shop` catalogue with product-line filter; `/shop/[sku]` product page.
- `/cart` (browser storage), `/checkout` (sign-in required), `/orders` (status timeline and a
  **Get help** button per order).
- Product pictures: per-product-line illustrations (icons), no external images.
- Demo delivery controls are shown only to administrators: on their own `/orders` page (an
  administrator can shop like a customer to stage a scenario) and on the order card of the
  staff complaint page. Customers never see them; the API enforces the admin role.

## 3. Support chat

### 3.1 Data

- **`chat_conversations`**: `id`, `customer_id`, `user_id`, `order_id` (nullable),
  `complaint_id` (nullable), `state` (`gathering` → `confirming` → `submitted`), `draft`
  (JSONB: title, requested resolution), `turns` (customer messages so far), timestamps.
- **`chat_messages`**: `id`, `conversation_id`, `role` (`customer` | `assistant`),
  `kind` (`text`, `order_options`, `summary`, `reference`, `reply`, `holding`,
  `acknowledgement`), `content` (redacted text), `payload` (JSONB: order buttons, summary
  fields), `created_at`.

### 3.2 Flow

1. **Start** (`POST /chat/conversations`, optional `order_ref`): deterministic greeting plus
   the customer's recent orders as buttons and "Something else"; if an order was given it is
   pre-selected and the bot asks what went wrong.
2. **Gathering** (`POST /chat/conversations/{id}/messages`): each customer message is
   sanitised and redacted, stored, then one GenAI call returns a structured
   **intake turn**: `{reply, title, missing: [..], ready_to_confirm: bool,
   requested_resolution | null}` (JSON schema, both providers). The bot asks one question at
   a time, only for essentials (what happened, which product/order, when, what the customer
   wants); after at most 6 customer messages it must summarise.
3. **Confirming**: the bot posts a summary card (title, the customer's own description,
   order, requested resolution) with **Confirm** / **Change something**.
4. **Submitted** (`POST /chat/conversations/{id}/confirm`): `submit_complaint` is called with
   `channel="live_chat"`, the selected order, the AI's title and requested resolution, and a
   **description built from the customer's own messages** (verbatim, redacted, joined in
   order). The bot posts the complaint reference. Analysis is queued as today.
5. **Reply**: when Pipeline 2 finishes (`python_validation.pipeline._apply`), a hook posts to
   the linked conversation:
   - verdict *verified* / *corrected*: the Pipeline 1 draft `customer_response.body`;
   - *needs review*: a holding message with the first-response SLA time. When a reviewer
     approves or modifies the response (`complaint_processing.review.apply_review`), the
     approved text is posted.
6. **After submission**: further customer messages are stored in the chat, added to the
   complaint timeline as customer-visible events, and acknowledged by a fixed message (no new
   analysis; reviewers can **Regenerate**).

Clients poll `GET /chat/conversations/{id}/messages?after=<id>` every 2 seconds while a
reply is pending, and stop once it arrives.

### 3.3 Intake prompt and safeguards

- New versioned template `prompt_templates/chat_intake.yaml` (name, version, hash recorded
  per call like the analysis prompt). Customer text is escaped inside tags and treated as
  data; the prompt forbids promising, deciding or estimating any remedy, amount or date.
- The intake call goes through the existing provider interface (`LLMProvider`) with its own
  JSON schema; the call is logged (provider, model, tokens, latency).
- **Promise guard**: every AI-written bot message is checked with
  `hallucination_checks.promises.find_promises`; a message containing a commitment is
  replaced by a neutral question.
- **Fallback** (provider unavailable, or invalid JSON twice): fixed questions in order ("What
  happened?", "When did it happen?", "What would you like us to do?"), then the summary step.
- The stored complaint description is always the customer's words; the AI title and
  requested resolution are shown to the customer for confirmation before submission.

### 3.4 Access and limits

- Only the conversation's customer can read or post to it (404 otherwise); staff read the
  transcript through the complaint (`GET /complaints/{ref}/chat`, staff only).
- Message length ≤ 2,000 characters; ≤ 30 customer messages per conversation; one open
  (`gathering`/`confirming`) conversation per customer and order.

### 3.5 Web

- Chat panel (sheet) opened from a floating bubble on shop pages and from **Get help** on an
  order; renders order buttons, summary card with Confirm / Change something, typing
  indicator while waiting.
- Complaint page (staff): **Chat transcript** card when the complaint came from chat.

## 4. Error handling

- Checkout re-prices from the server; unknown/inactive SKUs and invalid quantities → 422
  with all problems listed.
- Chat: 404 for foreign conversations; 409 when posting to a conversation in the wrong
  state (e.g. confirming twice); 422 for over-long messages or exceeding the message cap.
- Intake GenAI failures → fallback questions; complaint submission errors (e.g. intake
  validation) are shown in the chat as a bot message asking for the missing detail.
- Pipeline failures behave as today (Python-only validation, holding message).

## 5. Testing

- **Unit**: intake-turn schema validation; promise guard replaces committing bot messages;
  fallback question sequence; checkout line pricing and business-day delivery dates;
  description assembled from customer messages only.
- **Integration** (scripted GenAI provider): browse and checkout; order list; demo delivery
  controls admin-only; full chat → confirm → complaint created with `live_chat` and the
  customer's words → validation hook posts the reply; needs-review path posts the holding
  message and later the reviewer-approved reply; access control on conversations; state
  errors (409) and limits (422).
- **Frontend**: lint, typecheck, production build; manual walk-through of shop, checkout,
  chat and staff transcript in the browser.

## 6. Out of scope

Payments, real inventory, product search, reviews, emails, staff live-chatting with
customers (staff reply through existing reviewer actions), WebSockets.

## 7. Documentation

Short sections in `documentation/user_guide.md`, `documentation/demo_script.md` and
`documentation/project_report.md`; README feature list; `AI_USAGE.md` entry.
