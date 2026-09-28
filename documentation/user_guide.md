# User Guide (execution instructions)

How to use SupportNova, step by step, in the order the SRS lists (Execution Instructions,
deliverable 13). Screen names are those in the left sidebar.

| Role | What they can do |
|---|---|
| Customer | Submit complaints, track their own complaints |
| Agent | Complaint queue, work on complaints, knowledge base (read), rule matrix (read) |
| Reviewer | Everything an agent can, plus manual review, analytics and reports |
| Manager | Reviewer rights plus users & roles |
| Administrator | Everything, including uploading documents, editing rules, taxonomy and SLAs |

## 1. Log in

Open the site and choose **Sign in** (Clerk). The first sign-in with an e-mail listed in
`BOOTSTRAP_ADMIN_EMAILS` becomes an administrator; everyone else starts as a customer, and an
administrator changes roles under **Users & roles**.

## 2. Upload company documents

**Knowledge base → Upload document** (administrator).

1. Choose a PDF or DOCX file (TXT and Markdown also work).
2. Document ID, category, version and dates are read from the header lines at the top of the
   document (`Document ID: DEL-POL-04`, `Version: 2.0`, ...) or typed in the form.
3. Tick **Activate when processed** to make it the active version as soon as it is ready.
4. The status changes from *Processing* to *Ready*. **Chunks** shows the passages with their
   section, heading and page.

Uploading a new version of an existing document supersedes the old one, and open complaints
whose analysis relied on the old version are flagged for review. A passage that contains
instructions aimed at the AI is shown as *quarantined* and never used.

Bulk import: `uv run python -m knowledge_base.import_documents path/to/folder`.

## 3. Configure complaint rules

- **Rule matrix** (administrator: **New rule**, or the pencil icon to edit). Set the
  category and subcategory (or *Any* for escalation rules), a condition over the listed facts
  (for example `days_late > 5 and shipping_method == 'standard'`), the outcome (department,
  urgency, priority, escalation level), required and prohibited actions, policy references
  and follow-up. Each save is validated, versioned and audited. **Export CSV** downloads the
  matrix.
- **Taxonomy & SLAs**: categories, subcategories, departments and the response and
  resolution targets per priority.

## 4. Submit a complaint

- Customer: **Submit a complaint**. Choose the order it is about (or *No specific order*),
  describe what happened and what you would like us to do.
- Staff: **Complaint queue → Log a complaint** on behalf of a customer (customer reference).

Intake checks run immediately: too-short descriptions, unknown order references and exact
duplicates are rejected with a clear message; card numbers, passwords and ID numbers are
removed; risk signals (safety, injury, privacy, legal, injection...) are detected.

## 5. Analyse the complaint

Analysis starts automatically in the background (the worker must be running). On the
complaint page the status moves from *Analysis queued* to the result, usually within
20 seconds. **Re-run analysis** analyses again, for example after a policy update.

From the command line: `make analyze` (10 dataset complaints) or
`uv run python -m genai_pipeline.analyze --refs CMP-000012`.

## 6. Review the GenAI output

The **AI analysis (Pipeline 1)** section of the complaint page shows the structured JSON result:
summary, primary and secondary issues, sentiment and emotions, urgency with its rationale,
priority, department and supporting departments, cited policy passages, resolution steps,
compensation, escalation notes, the drafted customer response, follow-up, agent guidance,
missing information and clarification questions, and any suspicious instructions found.
The run information shows the prompt version, model, attempts, tokens and latency.

## 7. Run Python validation

Validation runs automatically after each analysis. **Ground-truth validation (Pipeline 2)**
on the complaint page shows the verdict (*Verified*, *Verified with corrections* or
*Needs review*), the score, why a human must review, what Python enforced, the field-by-field
GenAI vs Python table and every check with its evidence. **Re-validate** runs it again (for
example after a rule change).

## 8. Review mismatches

- On a complaint: the **GenAI vs Python** table marks every disagreement with an explanation.
- Across complaints: the dashboard's **GenAI vs Python agreement** panel, and
  **Reports → GenAI / Python Comparison** (preview or export).

## 9. Generate the customer response

The GenAI drafts the response. A reviewer uses **Reviewer decision**:

- **Approve**: send the draft as it is;
- **Modify response**: edit the text, then approve;
- **Regenerate**: run the GenAI again;
- **Reject**: handle manually (a comment is required).

The approved text appears as **Approved customer response**.

## 10. Escalate a complaint

Mandatory escalations are applied automatically by the rules (for example safety →
level 5, data exposure → level 4). To escalate manually: **Reviewer decision → Escalate**
and choose the level (it can never be lowered below what the rules require), or
**Status → Escalated**.

## 11. Review the manual queue

**Manual review** lists complaints that need a human decision, with the reasons: GenAI and
Python disagree, missing policy support, ambiguous complaint, unclear escalation, policy
contradiction, sensitive case (escalation level 4 or 5) or a policy that changed. Open one,
decide (approve, modify, reject, reclassify, reassign, escalate, regenerate, comment); the
decision history keeps the before and after state.

## 12. Track a complaint

- Customers: **My complaints** / the dashboard shows status, department, latest update and
  resolution; the complaint page shows the timeline.
- Staff: **Status → Update status** moves the complaint through the allowed statuses
  (New, Analyzed, Assigned, In progress, Awaiting customer, Escalated, Resolved, Closed,
  Reopened). SLA deadlines and status are shown on the complaint and in the queue.

## 13. View analytics

- **Dashboard**: role-specific. Agents see their department's queue; reviewers, managers and
  administrators see totals, distributions, SLA risks, trends, GenAI/Python agreement and
  review cases.
- **Analytics**: volume over time, category, product, department, urgency, sentiment,
  escalation, channel, customer type, resolution time, department performance, trends and
  policy usage. Filter by date range, category, department, priority, sentiment and channel.

## 14. Generate reports

**Reports**: choose one of the nine reports (Complaint Intelligence, Complaint Analysis,
Department Performance, Escalations, SLA Status, Policy Usage, Resolution Compliance,
GenAI / Python Comparison, Manual Reviews), set filters, preview, then **Export CSV**,
**Export Excel** or **Export PDF**.

From the command line: `make reports` writes the Complaint Intelligence Report to `reports/`.

## 15. Shopping and chat support (demo shop)

The public site at `/` is the VoltHaven demo shop; the staff console stays under
**Dashboard** (staff see a **Staff console** link in the shop header). The header has the
**Shop** menu (a tile per category), a **Support** menu, a product search with instant
suggestions and a slide-in cart; the footer has the newsletter sign-up (a demo: nothing is
ever sent), policy links and a light/dark switch. Pages: Home, Shop, product pages, Cart,
Checkout, My orders, About, Contact, Help centre, Shipping, Returns, Warranty, Privacy, Terms,
and *How our support works* (`/about-supportnova`).

1. **Browse** `/shop`: filter by category or price (presets or your own range), search, and
   sort by featured, best selling (orders in the last 90 days, lost parcels excluded), newest
   or price. Filters live in the address, so a filtered page can be shared.
2. **Product page**: photos (hover to zoom), specifications, quantity (1–5), **Add to cart**,
   an estimated arrival date, and Details / Shipping / Returns tabs.
3. **Cart**: change quantities or remove lines at `/cart` or in the slide-in cart.
4. **Checkout** (sign-in required): choose standard (within 5 business days) or express
   (within 2 business days); each option shows its arrival date. **Place order** shows a
   confirmation with the purchase reference. No payment is taken. Each product becomes its
   own order number (`ORD-8…`), grouped under one purchase reference (`CHK-…`).
5. **My orders** (`/orders`): status (processing, delivered, late by N business days, lost)
   and a delivery timeline per item.
6. **Get help** on an order (or **Nova**, the chat button on every shop page) opens the support chat:
   - general questions (delivery times, returns, refunds, warranty…) are answered with the
     Help-centre answer, word for word — the AI only picks which approved answer fits;
   - for a problem, the assistant asks one question at a time (what happened, when, what you
     would like), never the same question twice;
   - it then shows a summary with **Confirm** / **Change something**;
   - on Confirm the complaint is filed through the normal pipelines (channel *live chat*) and
     you get the reference immediately;
   - within about 20–40 seconds the reply appears in the chat if Python validation approved
     it; otherwise a specialist-review message appears, and the reply follows once a reviewer
     approves it in **Manual review**;
   - anything you write afterwards in that chat is added to the complaint's timeline (the
     reply says so); **New question** starts a fresh chat. Opening Nova again after a
     complaint was filed starts a fresh chat with a link to that complaint; Get help on the
     same order reopens that order's chat.
   The complaint text is always your own words; the assistant never promises refunds, dates
   or other outcomes.
7. **Contact us** (`/contact`): choose a topic.
   - *A problem with an order* needs sign-in; pick the order and describe the problem. It is
     filed as a complaint (channel *web form*) and analysed like any other.
   - Product questions, business enquiries, feedback and anything else become **enquiries**
     (`ENQ-…`). Card numbers, passwords and ID numbers are hidden before storage.
8. **Help centre** (`/help`): searchable questions and links to the Shipping, Returns and
   Warranty pages. Every number on those pages comes from `config/storefront.yaml`, and a test
   checks each one against the knowledge-base policy documents.

**Enquiries inbox (staff).** **Enquiries** in the sidebar lists contact-form messages that are
not complaints, filtered by status and topic. Open one to read it, **Reply by e-mail**,
**Mark handled** / **Reopen**, or **Convert to complaint** (only for messages sent by a
signed-in customer; the new complaint then goes through both pipelines).

**Demo delivery controls (administrators).** On their own **My orders** page and on a
complaint's order card, administrators see a **Demo** menu to make a delivery happen on time,
late (2, 5 or 8 business days), damaged or lost, to stage realistic complaints.

**Staff view.** Complaints from the chat show a **Chat transcript** card on the complaint page.

**Products (administrators).** **Products** in the staff console lists the catalogue. **New
product** takes a SKU (fixed once created), name, category, price, description and key specs;
save it, then add images. Each product takes up to 5 images (JPG, PNG or WebP, 5 MB each,
checked by content): drop them in or click to choose, use the arrows or the star to set the
order (the first is the main image), or delete them. **Show in shop** hides or shows a product
without deleting it, so existing orders and complaints keep working. Products without images
show a category illustration. `make seed` only adds catalogue products that are missing, so it
never overwrites these edits.

## 16. E-mail complaints

Customers can e-mail the support mailbox (for example `care@…`). Every minute the worker
reads new messages and:

- **opens a complaint** (channel *e-mail*) through the same checks and pipelines as every other
  channel, and e-mails back an acknowledgement with the reference, e.g. `[CMP-000123]`;
- **adds a reply** in that thread from the same customer to the existing complaint (quoted
  earlier messages and signatures are removed), including any attached photos or PDFs;
- **ignores** automatic mail (out-of-office replies, bounces, newsletters) so no mail loops
  happen;
- **answers** a message that is too short ("please tell us what happened…") or that repeats
  an open complaint (with its reference).

The customer then receives, by e-mail and in the same thread, a holding message if the case
needs specialist review, and the reply once Python validation or a reviewer approves it,
exactly as in the chat.

**Mailbox page (staff).** **Mailbox** in the sidebar shows whether the mailbox is configured
and when it was last checked, the **Received** e-mails with what happened to each, and the
**Sent** e-mails with their status (queued, sent, failed, or *not sent* when no mailbox is
set up). **Process an e-mail** runs an e-mail by hand — paste the sender, subject and text, or
upload a saved `.eml` file — exactly as if it had arrived; use it for demos or for complaints
forwarded from elsewhere.

**Setting up the mailbox (administrator).** Add the `MAIL_*` settings to `.env` (see
`.env.example`; for Gmail create an *App password*) and restart the API and worker.

## 17. Supporting documents

Photos (JPG, PNG, WebP) and PDFs, up to 5 MB each and 5 per complaint, can be attached:

- by customers from **My complaints** → the complaint → **Supporting documents → Add file**,
  or on the Contact us form when reporting a problem with an order;
- automatically from e-mail attachments;
- by staff on the complaint page (staff can also remove a document).

Files are checked by their content, not their name, and only the customer who owns the
complaint and staff can download them. The AI analysis is told how many photos and PDFs were
attached (it never reads the files), so replies do not ask for evidence already sent; the
Python validation report lists them as *Supporting evidence*.

## 18. Import complaints (managers and administrators)

**Import complaints** in the sidebar loads many complaints from one file, for example a batch
from the call centre.

1. Download the **CSV** or **Excel template**. Required columns: `customer_email`, `title`,
   `description`; optional: `customer_name`, `order_ref`, `channel` (default
   `phone_callback`), `received_at` (e.g. `2026-09-20` or `2026-09-20T10:30`),
   `requested_resolution`, `external_ref`. Up to 1,000 rows and 5 MB.
2. Upload the file. Every row is checked with the normal intake rules — nothing is saved yet —
   and marked *Ready*, *Warning* (e.g. no order reference, or instructions aimed at the AI) or
   *Error* (e.g. too short, unknown channel, date in the future, order not theirs, duplicate).
3. **Import** files the ready and warning rows (customers are matched by e-mail or created);
   each new complaint is analysed as usual. Download the **result** file for the reference or
   reason of every row. A file imported before is flagged, and its rows are skipped as
   duplicates.

## 19. Settings (administrators)

**Settings** (Administration in the sidebar) changes how SupportNova runs, without a redeploy.
Changes apply within about 15 seconds and every save is recorded in the audit trail with the
values before and after. API keys and passwords are not here: they stay on the server.

| Tab | What you can change |
|---|---|
| E-mail & timing | How often the mailbox is checked (60–3600 s) and queued e-mails are sent (15–600 s), the sender name, and whether automatic replies are sent. With automatic replies off, even verified replies go to **Manual review** and are sent when a reviewer approves them; the customer gets a holding message meanwhile. |
| AI | Provider (only those with an API key on the server), model, reasoning effort, policy passages read per complaint (3–20), and whether new complaints are analysed automatically. When off, start an analysis with **Re-run analysis**. |
| Operations | How often the SLA risk scan runs (1–60 min), the minimum score for *verified* (50–100) and the escalation level that always needs a human review (1–5). |
| Branding | Shop and console logos (PNG, JPEG or WebP, up to 1 MB; square works best; the shop logo is also the browser-tab icon), shop name and tagline, console name, support e-mail, phone, address and opening hours shown on the shop. |
| Policy facts | Read-only: warranty, returns and delivery numbers with the policy document they come from. To change one, upload a new version of that document in the **Knowledge base**, so the shop, the AI and the rules always agree. |

If two administrators edit at once, the second save is refused with *Someone else changed the
settings; reload*.
