# Deployment

Target: the web app on **Vercel**, the API, worker and scheduler on **Railway**, files on
**Cloudflare R2**, sign-in with **Clerk**, analysis with the **Anthropic API** or the **OpenAI API** (one setting). All services
have free or trial tiers that are enough for the demonstration.

```
Browser ──► Vercel (Next.js, web/) ──► Railway: api (FastAPI) ──► Railway: PostgreSQL + pgvector
                                             │                     Railway: Redis
                                             │                         ▲
                                             │        Railway: worker (Celery) ── Anthropic / OpenAI API
                                             │                                 ── support mailbox (IMAP in; SMTP or Brevo out)
                                             │        Railway: beat (one tick every 15 s; the SLA scan,
                                             │                       mailbox check and e-mail outbox run
                                             │                       on the intervals set in Settings)
                                             └──► Cloudflare R2 (uploaded documents and attachments)
```

Keys are pasted into each platform's settings. **Never commit them.**

## 0. Before you start

1. The code is on GitHub (public repository).
2. Accounts: GitHub, Vercel, Railway, Cloudflare, Clerk, and Anthropic (console.anthropic.com)
   or OpenAI (platform.openai.com). Optional: a Gmail account for e-mail complaints
   (see `.env.example` for the App password steps).
3. Decide who the evaluators are: you will create their sign-in accounts in step 6.

## 1. Cloudflare R2 (file storage)

1. Cloudflare dashboard → **R2** → **Create bucket**, name `supportnova`.
2. **R2 → Manage API tokens → Create API token** with *Object Read & Write* on that bucket.
3. Keep these values for step 3: the **S3 endpoint** (`https://<account-id>.r2.cloudflarestorage.com`),
   the **Access Key ID** and the **Secret Access Key**.

## 2. Clerk (sign-in)

A Clerk *development* instance is fine for the demonstration (it shows a small "development"
badge). A *production* instance needs your own domain.

1. Use the application you already created, or create a new one.
2. **Configure → API keys**: note the Publishable key, the Secret key and the Frontend API URL.
   If a secret key was ever shown or shared, **roll it** here first and use the new one.
3. **Sessions → Customize session token** must contain
   `{ "email": "{{user.primary_email_address}}", "name": "{{user.full_name}}" }` (already
   done if you followed the local setup).

## 3. Railway (API, worker, scheduler, database, Redis)

1. railway.com → **New project → Deploy from GitHub repo** → pick the repository. This creates
   the first service; rename it **api**.
2. In the project: **+ New → Database → PostgreSQL**. The app needs the `vector` extension:
   use Railway's **pgvector** template (search "pgvector" under *+ New → Template*) if the
   standard PostgreSQL service does not have it. The first migration runs
   `CREATE EXTENSION IF NOT EXISTS vector`.
3. **+ New → Database → Redis**.
4. **+ New → GitHub repo** (same repository) twice more, and name the services **worker** and
   **beat**.
5. For each of the three code services open **Settings → Config-as-code** and set the file:

   | Service | Config file |
   |---|---|
   | api | `deploy/railway/api.json` (runs migrations before each release, health check `/readyz`) |
   | worker | `deploy/railway/worker.json` |
   | beat | `deploy/railway/beat.json` (exactly one instance) |

6. **Variables**: add these to *api*, *worker* and *beat* (Railway's *Shared variables* saves
   typing them three times):

   | Variable | Value |
   |---|---|
   | `ENVIRONMENT` | `production` |
   | `DATABASE_URL` | reference the PostgreSQL service's `DATABASE_URL` (the app converts `postgresql://` automatically) |
   | `REDIS_URL` | reference the Redis service's `REDIS_URL` |
   | `ALLOWED_ORIGINS` | your Vercel address, e.g. `https://supportnova.vercel.app` |
   | `CLERK_ISSUER` | Clerk Frontend API URL |
   | `CLERK_AUTHORIZED_PARTIES` | the same Vercel address |
   | `BOOTSTRAP_ADMIN_EMAILS` | your e-mail (and any administrator's) |
   | `STORAGE_BACKEND` | `s3` |
   | `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | from step 1 |
   | `GENAI_PROVIDER` | `anthropic` or `openai` |
   | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | for Claude (e.g. `claude-opus-5`) |
   | `OPENAI_API_KEY`, `OPENAI_MODEL` | for OpenAI (e.g. `gpt-5-mini`) |
   | `MAIL_IMAP_HOST`, `MAIL_IMAP_PORT`, `MAIL_SMTP_HOST`, `MAIL_SMTP_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_FROM_NAME` | optional: the support mailbox for e-mail complaints (Gmail: `imap.gmail.com` 993, `smtp.gmail.com` 465, an App password). The *worker* reads and sends the mail (beat only schedules it) and the *api* shows its status, so set them on both — shared variables do that |

   | `MAIL_SEND_VIA`, `BREVO_API_KEY` | **Railway blocks outbound SMTP below the Pro plan** (e-mails fail with `Network is unreachable` or time out; reading over IMAP still works). Set `MAIL_SEND_VIA=brevo` and a Brevo API key on *worker* and *api* to send over HTTPS instead: create a free account at brevo.com, **Senders → Add a sender** with the `MAIL_USERNAME` address and confirm the e-mail Brevo sends, then **SMTP & API → API keys → Generate**. Replies still come back to the Gmail inbox (Reply-To) |

   Use a mailbox that no other SupportNova (e.g. your local `make worker`) is reading: two
   workers on one inbox each take whichever new e-mails they see first.

   E-mails that failed before sending was fixed can be sent again from the *worker* shell:
   `python -m email_channel.retry`.

   The API refuses to start in production if the Clerk issuer, the CORS origin or R2 storage
   is missing, so misconfiguration shows up in the deploy log instead of at run time.
7. *api* → **Settings → Networking → Generate domain**. Note the address, e.g.
   `https://supportnova-api.up.railway.app`. Check `https://<api-address>/healthz` returns
   `{"status":"ok"}`.
8. Load the data once. In the *api* service, open a shell (**⋯ → Shell**, or `railway ssh`
   with the Railway CLI) and run:
   ```bash
   python -m database.bootstrap --with-holdout
   ```
   This seeds the taxonomy and 111 rules, imports the 20 policy documents and loads the
   536-complaint dataset and the 109-complaint hold-out pack. It is safe to run again.

## 4. Vercel (web app)

1. vercel.com → **Add New → Project** → import the repository.
2. **Root Directory**: `web`. Framework: Next.js (detected).
3. **Environment variables**:

   | Variable | Value |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | the Railway API address from step 3.7 |
   | `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk publishable key |
   | `CLERK_SECRET_KEY` | Clerk secret key |
   | `NEXT_PUBLIC_CLERK_SIGN_IN_URL` | `/sign-in` |
   | `NEXT_PUBLIC_CLERK_SIGN_UP_URL` | `/sign-up` |
   | `NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL` | `/dashboard` |
   | `NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL` | `/dashboard` |

4. **Deploy**. If the Vercel address differs from what you put in `ALLOWED_ORIGINS` and
   `CLERK_AUTHORIZED_PARTIES`, update those on Railway and redeploy the API.

## 5. Clerk webhook (keeps users in sync)

Clerk → **Configure → Webhooks → Add endpoint**:
`https://<api-address>/api/v1/webhooks/clerk`, events `user.created`, `user.updated`,
`user.deleted`. Copy the signing secret into `CLERK_WEBHOOK_SIGNING_SECRET` on Railway.

## 6. Evaluator and administrator accounts

1. Sign in on the deployed site with your administrator e-mail (from
   `BOOTSTRAP_ADMIN_EMAILS`): you become an administrator.
2. Clerk → **Users → Create user** for each evaluator account (e-mail and password), e.g.
   `evaluator.admin@…`, `evaluator.reviewer@…`, `evaluator.agent@…`, `evaluator.customer@…`.
3. Each evaluator signs in once (this creates their SupportNova record), then in SupportNova
   **Users & roles** set their role (administrator, reviewer, agent, customer).
4. Put the site address and these credentials in the submission form only, not in the
   repository.

## 7. Smoke test after deployment

1. Sign in as administrator: the dashboard loads with the dataset.
2. **Knowledge base**: 20 active documents.
3. Submit a complaint as the customer account; within about 20 seconds it shows an analysis
   and a validation verdict (the worker processes it).
4. **Reports**: export the Complaint Intelligence Report as PDF.
5. Railway *beat* logs show `app_settings.tasks.tick` every 15 seconds; the SLA scan, mailbox
   check and outbox run on the intervals in **Settings** (defaults 5 min, 1 min, 30 s). The
   pre-deploy migration creates the `app_settings` and `job_runs` tables (and, with the orders
   release, `order_events` and `fx_rates`; existing orders get a stage matching their status).
   The worker needs outbound HTTPS to `open.er-api.com` for the twice-daily exchange rates;
   without it, PKR uses the fallback rate in **Settings → Orders**.
6. If the mailbox is configured: send a complaint e-mail to it. Within about a minute
   **Mailbox** shows it under *Received → New complaint* and the acknowledgement under *Sent*,
   and the sender receives it with the `[CMP-…]` reference.
7. As a manager, **Import complaints** → download the CSV template → upload it → Import: one
   complaint is created.

## 8. Running costs and limits

- Railway's trial or hobby plan covers five small services. Stop the worker and beat when the
  demonstration period ends (this also stops the mailbox check).
- Each complaint analysis is one or two GenAI calls. Re-analysing all 645 complaints costs
  real money: analyse a sample (`make analyze` does 10) plus the hold-out pack for the
  comparison report.
