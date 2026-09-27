# VoltHaven storefront redesign: design

Date: 2026-09-27 · Status: approved in conversation, awaiting spec review
Builds on: `2026-09-26-storefront-and-support-chat-design.md` (shop, chat) and the product
management feature (products and images).

## 1. Purpose

Make the public VoltHaven site look and behave like a real, premium e-commerce website for the
demonstration video and evaluators: a complete set of pages, polished motion, working search,
filters and sorting, a Contact us form that feeds the complaint pipeline or an enquiries inbox,
and policy pages whose numbers provably match the knowledge base the AI and rules use.

**Success criteria**

- Every page listed in §3 exists, works on phone and desktop, in light and dark mode, and with
  reduced motion.
- Home shows real best sellers (from orders) and new arrivals (from product creation dates).
- Catalogue search, category and price filters and sorting work on real data.
- Contact us: complaint topic (signed in) → complaint via the normal intake (`web_form`);
  other topics → enquiry in a staff inbox.
- Every number on policy pages comes from `config/storefront.yaml`, and a test proves those
  numbers appear in the knowledge-base policy documents.

**Decisions taken**

| Question | Decision |
|---|---|
| Look and feel | Premium tech: light, generous white space, large product photos, one accent colour (electric blue), smooth motion |
| Pages | Header with mega-menu and search; home; shop; product; cart/checkout/orders restyled; About, Contact, Help/FAQ, Shipping, Returns, Warranty, Privacy, Terms; footer |
| Contact us | Split by topic: complaint → complaint pipeline (sign-in required); others → enquiries inbox |
| Approach | `motion` library for animation; one shared `config/storefront.yaml` for company and policy facts, served by the API |

## 2. Visual system

- Light theme by default for the shop; dark mode via a footer toggle (next-themes, already
  installed). Staff console unchanged.
- Palette: white and soft neutral greys; one accent (electric blue) for primary actions,
  links and highlights, defined as CSS tokens so dark mode inverts cleanly.
- Typography: Geist (already loaded); large, tight headlines (`tracking-tight`), muted
  secondary text; rounded-2xl cards; product photos on white.
- Motion (`motion` package): scroll-reveal (fade + rise, staggered for card grids), hero word
  reveal and floating product with soft glow and slight parallax, hover lift/zoom on cards,
  count-up numbers, animated cart badge and "fly to cart" dot, sheet transitions, page fade.
  All motion disabled under `prefers-reduced-motion` (`MotionConfig reducedMotion="user"`).
- Loading: skeletons for data; images lazy-loaded; friendly error state when the API is down;
  styled 404.

## 3. Pages

| Route | Content |
|---|---|
| Header (all shop pages) | Transparent over hero → frosted on scroll; Shop mega-menu (category tiles with images, "View all"); Support menu (Help centre, Track order, Contact, Chat with us); search with instant suggestions (→ `/shop?q=`); cart with mini-cart sheet; account (Clerk); mobile slide-in menu |
| `/` Home | Hero; category row; New arrivals and Best sellers carousels; feature spotlight (one product, count-up specs); Why VoltHaven (4 facts from config); support callout (opens chat); newsletter strip |
| `/shop` | Filter sidebar (category with counts, price range, in stock) / sheet on mobile; sort (featured, price ↑↓, newest, best-selling); search results; animated grid |
| `/shop/[sku]` | Gallery with thumbnails and hover zoom; price; specs; quantity; Add to cart (fly-to-cart); delivery estimate from config ("Order today, arrives by …"); tabs Details / Shipping / Returns; You may also like |
| `/cart`, `/checkout`, `/orders` | Restyled; mini-cart sheet; two-column checkout; animated "Order placed" confirmation |
| `/about` | Fictional company story, values, numbers from config |
| `/contact` | Form (name, email, topic, order for signed-in customers, message) + address, phone, e-mail, hours |
| `/help` | Searchable FAQ accordion (from config) + links to policy pages and chat |
| `/shipping`, `/returns`, `/warranty` | Article layout with side table of contents; figures from config |
| `/privacy`, `/terms` | Article layout; fictional-company notice |
| Footer | Columns Shop / Support / Company / Legal; newsletter; social icons; theme toggle; "VoltHaven Electronics is a fictional company created for a student project" |

The current `/about` (SupportNova explainer) moves to `/about-supportnova` and is linked from
the footer ("How our support works").

## 4. Backend

### 4.1 Shared shop config

`config/storefront.yaml`: company (name, address, phone, support e-mail, hours, socials),
shipping (standard/express business days, late-credit percent, cap, threshold days), returns
(window days, refund processing days), warranty (months), and FAQ entries. Served at
`GET /storefront/config` (public). `storefront.orders.SHIPPING_DAYS` reads the same values.
Test: each policy number appears in its knowledge-base source document
(`sample_documents/sources/`), e.g. delivery credit % and cap in DEL-POL-04, return window in
REF-POL-01, warranty length in WAR-POL-02.

### 4.2 Catalogue queries

`GET /products` adds `q` (name, description, specs; case-insensitive), `min_price`,
`max_price`, `sort` (`featured` default, `price_asc`, `price_desc`, `newest`,
`best_selling`). Best-selling = count of order lines per product in the last 90 days,
excluding status `lost`; ties by name.

### 4.3 Contact and enquiries

- `POST /contact` (public; Clerk token optional): `name`, `email`, `topic`
  (`order_problem`, `product_question`, `business`, `feedback`, `other`), `message`,
  optional `order_ref`, honeypot `website` (non-empty → 200 with no record).
- `order_problem`: requires sign-in (401 with a clear message otherwise); the order must be
  the customer's; filed via `submit_complaint` (channel `web_form`), returns the complaint
  reference.
- Other topics: stored as an `Enquiry` (`ENQ-000001`), message sanitised and redacted like
  complaints; returns the enquiry reference.
- Staff (agent and above): `GET /enquiries` (filter by status, topic), `PATCH
  /enquiries/{ref}` (`status`: `new` | `handled`), `POST /enquiries/{ref}/convert` (creates a
  complaint when the enquiry is linked to a customer account; 422 otherwise). All audited.
- Table `enquiries`: ref, name, email, topic, message, user_id, customer_id, status,
  handled_by_id, handled_at, complaint_id (after conversion), created_at.

### 4.4 Newsletter

`POST /newsletter` (public): `email`, `source`; stored once (idempotent); table
`newsletter_subscribers` (email unique, source, created_at). The UI states that it is a demo
and nothing is sent.

## 5. Testing

- Config: numbers match knowledge-base documents; checkout delivery days come from config.
- Catalogue: `q`, price filters, each sort; best-selling counts real orders, excludes lost and
  >90-day-old orders; hidden products never listed.
- Contact: enquiry stored and redacted; complaint topic (signed in) creates a `web_form`
  complaint and queues analysis; complaint topic signed out → 401; honeypot drops silently;
  foreign order → 404.
- Enquiries: staff-only (customer 403), mark handled, convert (only with an account), audited.
- Newsletter: idempotent; invalid e-mail → 422.
- Frontend: lint, typecheck, production build; browser walk-through of every page at desktop
  and phone widths, light and dark, and reduced motion.

## 6. Out of scope

Payments, reviews and ratings (would be invented), wishlists, sending newsletters, multiple
languages or currencies, a CMS for page text.

## 7. Order of work

1. Backend: config endpoint, catalogue queries, contact, enquiries, newsletter (with tests).
2. Design foundation: tokens, motion setup, header, footer, mini-cart.
3. Home. 4. Shop and product. 5. Cart, checkout and orders restyle.
6. Company and help pages. 7. Contact page and staff Enquiries inbox.
8. Browser walk-through, docs, final review.
