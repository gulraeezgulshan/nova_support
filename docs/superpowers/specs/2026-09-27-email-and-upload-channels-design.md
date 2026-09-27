# Email complaints, supporting documents and bulk upload: design

Date: 2026-09-27 · Status: approved in conversation, awaiting spec review
Builds on: the complaint intake (`complaint_processing.service.submit_complaint`), the support
chat reply hooks (`support_chat.notify`), file storage (`src.core.storage`) and the Celery
worker/beat (`src/worker.py`).

## 1. Purpose

The SRS names e-mail as a complaint source and "supporting documents" as a complaint field;
its channel figure shows web form, e-mail, chat and complaint upload. The web form (Contact
us) and chat exist. This adds the remaining two channels and supporting documents:

- **E-mail:** complaints sent to a real mailbox are filed automatically; customers get an
  acknowledgement and, once approved, the reply by e-mail in the same thread.
- **Supporting documents:** photos and PDFs attached to a complaint (from e-mail, the
  Contact us form, the customer's complaint page, or staff).
- **Bulk upload:** staff upload a CSV/Excel file of complaints with a preview and a per-row
  result.

**Success criteria**

- Sending an e-mail to the configured mailbox creates a complaint within about a minute and
  the sender receives an acknowledgement with the reference; the approved reply follows by
  e-mail; a reply in that thread is added to the same complaint.
- Without mailbox settings everything else still works, and staff can process a pasted or
  uploaded `.eml` e-mail exactly as a received one (demo path).
- Customers and staff can attach photos/PDFs to complaints; only staff and the owning
  customer can download them.
- A 1,000-row CSV or `.xlsx` can be previewed without saving anything, then imported;
  every row gets a reference or a reason.

**Decisions taken**

| Question | Decision |
|---|---|
| E-mail intake | Real mailbox checked every minute by the worker (IMAP), plus a staff "Process an e-mail" tool |
| Replies | Acknowledgement, holding message when under specialist review, approved reply; SMTP from the same mailbox |
| Complaint upload | Both: staff bulk upload (CSV/Excel) and supporting documents on individual complaints |
| Approach | Celery Beat task with Python's standard `imaplib`/`smtplib`/`email`; no new process |

## 2. E-mail channel

### 2.1 Settings

`.env` (the user adds values; never committed): `MAIL_IMAP_HOST`, `MAIL_IMAP_PORT` (993),
`MAIL_SMTP_HOST`, `MAIL_SMTP_PORT` (465 SSL or 587 STARTTLS), `MAIL_USERNAME`,
`MAIL_PASSWORD`, `MAIL_FROM_NAME` ("VoltHaven Customer Care"). The mailbox is "configured"
when host, username and password are present. Not configured: the scheduled check does
nothing, outgoing e-mails are recorded with status `not_configured`, and the console says
so.

### 2.2 Receiving

- Beat task `email_channel.tasks.check_mailbox` every 60 s. A Redis lock (TTL 5 min) stops
  overlapping runs. It reads up to 25 unseen messages from `INBOX`, processes each, and
  marks it seen (also when ignored or rejected, so it is never re-read). A connection or
  login failure is logged and recorded as the mailbox's last error; the next run retries.
- Every message is recorded in `inbound_emails` (see 2.5) keyed by `Message-ID` (unique; a
  missing ID gets a hash of sender + date + subject), so nothing is processed twice.
- **Ignored (recorded, no reply):** `Auto-Submitted` other than `no`, `X-Autoreply`,
  `Precedence: bulk|list|junk`, `List-Id`, senders `mailer-daemon`/`postmaster`, and
  messages from our own address.
- **Thread replies:** a message whose subject contains `[CMP-000123]` or whose
  `In-Reply-To`/`References` matches one of our outbound `Message-ID`s, sent from that
  complaint's customer address, is added to that complaint as a `customer_message` event
  (same as chat follow-ups); its attachments are added (§3). From another address: treated
  as a new complaint.
- **New complaint:** through `submit_complaint` with `channel="email"`, `source="email"`,
  `external_ref=<Message-ID>`:
  - title: subject without `Re:`/`Fwd:` prefixes (or the first line of the body if empty);
  - description: `text/plain` part (else HTML converted to text), with quoted history
    (`>` lines, "On … wrote:" and below) and signatures (`-- ` and below) removed;
  - customer: matched by e-mail to an existing customer (or a user's customer record),
    else created (`CustomerType.STANDARD`, name from the `From` display name);
  - order: the first `ORD-\d{6}` in subject or body, linked only if it belongs to that
    customer (otherwise ignored, not an error);
  - redaction, duplicate detection, risk signals and both pipelines run as for any channel.
- **Outcomes** (`inbound_emails.outcome`): `filed`, `appended`, `ignored`, `rejected`
  (validation failed → reply listing what is missing), `duplicate` (reply with the existing
  reference), `failed` (unexpected error; logged with the error message; the message is
  not marked seen so the next run retries, at most 3 attempts, then `failed` permanently).

### 2.3 Sending

- `outbound_emails` rows are created in the same transaction as the event that causes them
  and sent afterwards by the Celery task `email_channel.tasks.send_email` (3 retries with
  back-off). Statuses: `queued`, `sent`, `failed`, `not_configured`.
- Messages (plain text, company signature; the body of the reply is the approved text):
  - **Acknowledgement** on a new e-mail complaint: reference, what happens next.
  - **Holding message** when validation sends the case to specialist review (once).
  - **Reply** when Python validation approves the draft, or a reviewer approves/modifies
    it — hooked into the same points as `support_chat.notify.after_validation` and
    `after_approval`, only for complaints with `channel == "email"`.
  - **Rejected/duplicate** answers from 2.2.
- Threading: subject `Re: <original subject> [CMP-000123]`; `In-Reply-To` and `References`
  set to the customer's message ID; our own `Message-ID` stored for matching replies.
- Outbound text never contains data the customer did not send (no internal notes,
  validation details or other customers' data); the reply is the approved customer
  response only.

### 2.4 Staff console: Mailbox

Page **Mailbox** (agent and above): status line (configured / not configured, last check,
last error), tabs **Received** (time, from, subject, outcome, linked complaint) and **Sent**
(time, to, kind, status, linked complaint), and **Process an e-mail**: upload a `.eml` file
or paste from / name / subject / body (+ attachments). It runs the same code as a received
message (outcome shown, replies queued as normal; `not_configured` without SMTP).

### 2.5 Data

- `inbound_emails`: id, message_id (unique), from_address, from_name, subject, received_at,
  outcome, reason, complaint_id, attempts, via (`imap` | `manual`), created_at.
- `outbound_emails`: id, complaint_id, to_address, kind (`acknowledgement`, `holding`,
  `reply`, `rejected`, `duplicate`), subject, body, message_id, in_reply_to, status, error,
  sent_at, created_at.
- `mailbox_state` (single row): last_check_at, last_error.
- Raw message bodies are not kept beyond what the complaint stores (redacted description).

## 3. Supporting documents

- Allowed: JPEG, PNG, WebP, PDF, detected from file contents (magic bytes); ≤ 5 MB each;
  ≤ 5 per complaint. Others are refused with a clear message (API 422); e-mail attachments
  of other types are skipped and noted on the complaint timeline.
- Sources: `email` (new complaint or thread reply), `customer` (Contact us order-problem
  form; the customer's complaint page), `staff` (complaint page).
- Table `complaint_attachments`: id, complaint_id, filename (sanitised with
  `safe_filename`), media_type, size_bytes, storage_key, source, uploaded_by_id,
  created_at. Files stored through `get_storage()` under `complaints/<complaint_id>/`.
- API: `POST /complaints/{ref}/attachments` (owner customer or staff),
  `GET /complaints/{ref}/attachments`, `GET /complaints/{ref}/attachments/{id}` (download
  with `Content-Disposition: attachment`, `X-Content-Type-Options: nosniff`; owner or
  staff), `DELETE …/{id}` (staff). All audited.
- UI: a **Supporting documents** card on the complaint page (staff and customer views):
  photo thumbnails, PDF icon, download, source; add button (customer: own complaint; staff).
  Contact us order-problem form gets an attachment field: after `POST /contact` returns the
  complaint reference, the page uploads the files to `POST /complaints/{ref}/attachments`
  (the signed-in customer owns the complaint); a failed upload is reported without
  undoing the complaint. The chat's confirmation message
  mentions adding photos from My complaints.
- GenAI and Python: files are never sent to the model. The analysis prompt gets one
  untrusted-safe line, e.g. "Supporting documents attached: 2 photos, 1 PDF", so drafts do
  not ask for evidence already sent. Validation records an informational check
  "Evidence attached (n)" in its report; no rule changes.

## 4. Bulk complaint upload

- Page **Import complaints** (manager and admin). Template downloads: CSV and `.xlsx` with
  one example row.
- Columns: `customer_email`*, `customer_name`, `title`*, `description`*, `order_ref`,
  `channel` (one of the configured complaint channels; default `phone_callback`),
  `received_at` (ISO date or date-time; default now; not in the future), `requested_resolution`,
  `external_ref`. Header names are case-insensitive; unknown columns are listed and ignored.
- Limits: `.csv` (UTF-8, optional BOM) or `.xlsx`; ≤ 5 MB; ≤ 1,000 data rows.
- `POST /imports/preview` (multipart): parses and validates every row without writing —
  the intake's own checks (`validate_input`, order ownership for existing customers,
  exact duplicates against stored complaints and within the file) plus injection-signal
  warnings. Returns a batch preview id (stored in `import_batches` with status `previewed`
  and the parsed rows), per-row status `ready` | `warning` | `error` with messages, and a
  note if a file with the same SHA-256 was imported before.
- `POST /imports/{id}/run`: imports `ready` and `warning` rows in a background Celery task
  through `submit_complaint` (`source="upload"`, `created_at=received_at`,
  `external_ref`); customers matched by e-mail or created; each complaint queued for
  analysis. Status `running` → `done` with counts created / skipped / failed; rows that fail
  at import time (e.g. a duplicate created meanwhile) get their reason.
- `GET /imports`, `GET /imports/{id}` (progress and rows), `GET /imports/{id}/result.csv`
  (row number, status, reference or reason; cells starting with `=`, `+`, `-`, `@` are
  prefixed with `'`).
- Table `import_batches`: id, filename, sha256, uploaded_by_id, status, total, created,
  skipped, failed, rows (JSONB: parsed values + status + messages + reference), created_at,
  finished_at. `complaints.import_batch_id` (nullable FK). Preview and run are audited.
- Previewed batches not run within 24 hours are ignored by the run endpoint (409, preview
  again).

## 5. Security

- E-mail bodies, subjects, file names, spreadsheet cells and attachments are untrusted:
  sanitised, redacted and passed to GenAI only through the existing untrusted-text path.
- Mailbox password only in `.env`/platform secrets; never logged or returned by the API.
- Attachment and import endpoints enforce roles on the server; file type by content, not
  name; downloads never inline-render user files.
- Outbound e-mails go only to the address that sent the complaint (or the customer's stored
  address); no user-supplied recipient.

## 6. Testing

- E-mail parsing (unit): plain/HTML/multipart, quoted-history and signature trimming,
  `Re:`/`Fwd:` stripping, order-ref detection, auto-reply/list detection, attachment
  extraction, header-encoded names and subjects.
- Receiving (integration, fake IMAP client): new complaint filed with channel `email` and
  acknowledgement queued; thread reply appended; foreign sender on a thread → new
  complaint; duplicate and too-short replies; ignored auto-replies; idempotent on the same
  `Message-ID`; failure retried then marked failed; not-configured no-op; lock prevents
  overlap.
- Sending (integration, fake SMTP): acknowledgement, holding, reply after validation
  approval and after reviewer approval — only for e-mail complaints, once each; threading
  headers; retries; `not_configured`.
- Attachments: type/size/count limits, disguised files refused, owner vs other customer vs
  staff access, download headers, audit, e-mail attachments saved, evidence line in the
  prompt input.
- Bulk upload: CSV and `.xlsx`, BOM, header case, missing/unknown columns, row errors,
  in-file duplicates, future dates, 1,001 rows refused, preview writes nothing, run creates
  complaints with `source="upload"` and batch link, result CSV formula escaping, re-upload
  warning, expired preview, manager/admin only.
- Frontend: lint, typecheck, build; browser check of Mailbox, Import complaints, and the
  supporting-documents card.

## 7. Out of scope

Reading attachment contents with AI (OCR/vision), HTML e-mail templates, multiple
mailboxes, per-agent e-mail sending, IMAP IDLE/instant delivery, virus scanning (files are
type-checked and never rendered inline), bulk upload of attachments.

## 8. Order of work

1. Supporting documents (table, storage, API, complaint-page card, Contact us field, prompt
   line, validation note).
2. E-mail parsing and processing (shared by IMAP and the manual tool), tables, outbound
   queue and sending, notify hooks.
3. Mailbox check task and settings; Mailbox console page with Process an e-mail.
4. Bulk upload (preview, run, result, page).
5. Docs, browser walk-through, final review.
