# Test Cases

SRS deliverable 11. 432 automated backend tests (`make test`, pytest against a real
PostgreSQL + pgvector database) plus static checks (`make lint`: ruff, mypy `--strict`,
ESLint, TypeScript) and the production web build. CI runs all of them on every push
(`.github/workflows/`).

Folders: `tests/unit` (no database), `tests/integration` (database and HTTP API),
`tests/security` (adversarial suite). The GenAI provider is replaced by a scripted test
double in automated tests; live GenAI runs are covered by `make evaluate` (see
`documentation/evaluation.md`).

| SRS category | Tests (file :: test) |
|---|---|
| Functional | `integration/test_storefront_api.py`, `unit/test_storefront_orders.py`, `unit/test_catalogue.py`, `integration/test_catalogue_queries.py` (search, price range, sorting, real best sellers, literal search of `%`, `_` and `\`), `unit/test_storefront_config.py` (every figure on the shop's policy pages appears in its knowledge-base document) (shop); `integration/test_validation_and_review.py` (verify, correct, review queue, approval, reclassify, status), `integration/test_analytics.py` (dashboards, analytics, reports), `integration/test_taxonomy_api.py`, `integration/test_rules_api.py` |
| Complaint submission | `integration/test_email_channel.py` (e-mail: filed with channel e-mail, acknowledgement queued, thread replies appended without the quote, other sender on a thread is a new complaint, auto-replies ignored, too-short and duplicate answered, known customer and own order linked, holding and approved reply once, end to end through validation and review), `integration/test_mailbox_tasks.py` (scheduled check with fake IMAP/SMTP: not configured, lock, retries then give up, login failure, outbox retries and threading headers, Beat schedule), `integration/test_mailbox_api.py`, `unit/test_email_parsing.py` (encoded names, HTML, quoted history, automated mail, attachments); `integration/test_bulk_import.py` and `unit/test_import_reader.py` (bulk upload: preview writes nothing, row errors, in-file and stored duplicates, run, result file, re-upload, expiry, roles); `integration/test_contact.py` (Contact us: order problems need sign-in and become web-form complaints, double submit rejected, someone else's order rejected, other topics become redacted enquiries, honeypot, staff-only enquiries inbox, convert only once and only with an account, audited, newsletter idempotent); `integration/test_chat_api.py` (chat intake → confirm → complaint in the customer's words; double confirm; too-short description; access; limits), `integration/test_chat_replies.py` (reply / holding message / reviewer approval in the chat, no duplicates), `unit/test_chat_intake.py` (promise guard, invalid output, fallback), `integration/test_complaints_api.py` :: customer submits and it is queued, staff must name the customer, validation errors all reported, unknown or foreign order rejected, customers only see their own; `unit/test_complaint_intake.py` :: every problem is reported, valid input is cleaned |
| Document upload | `integration/test_attachments_api.py` and `unit/test_attachments.py` (supporting documents: type by content, limits, safe names, owner/staff access, audit, evidence line for the AI and Python); `integration/test_documents_api.py` :: upload, ingest and search the active policy, duplicate file and version rejected, invalid metadata, non-admin cannot upload; `unit/test_validation.py` :: real PDF/DOCX accepted, disguised, empty, oversized and unsupported files rejected, metadata rules |
| Parsing | `unit/test_parsers.py` :: PDF sections/headings/pages, DOCX heading styles, Markdown, ligatures, label lines, corrupt PDF; `unit/test_chunking.py` (5 tests); `unit/test_sample_documents.py` |
| GenAI API | `unit/test_openai_provider.py` (OpenAI adapter: request shape, strict schema, refusal, truncation, errors, provider switch); `integration/test_analysis_pipeline.py` :: valid first answer, invalid answer retried with the errors, still invalid → manual review, refusal not treated as an answer, provider outage, permanent error not retried; `integration/test_validation_and_review.py` :: GenAI outage still escalates a safety complaint |
| JSON | `unit/test_genai_contract.py` :: schema satisfies structured-output rules, enums come from the vocabulary, schema version changes with the taxonomy, missing field and bad JSON, vocabulary violations, valid output passes |
| Classification | `unit/test_validation_checks.py` :: correct analysis verified, vague complaint not guessed; `unit/test_dataset.py` :: labels agree with the rule matrix; `make report-baseline`, `make evaluate-python` |
| Routing | `unit/test_rule_engine.py` :: most specific rule wins, multi-issue complaint routes to the most severe department, unknown subcategory and brand-new category fall back |
| Urgency | `unit/test_rule_engine.py` :: calm safety complaint is critical, furious but low-risk stays low, VIP minor issue not prioritised; `unit/test_validation_checks.py` :: tone-driven priority is only a warning |
| Escalation | `unit/test_rule_engine.py` :: legal threat, low-value privacy breach, third complaint, injection; `unit/test_validation_checks.py` :: escalation trap enforced; `integration/test_validation_and_review.py` :: missed escalation corrected by Python |
| Resolution | `unit/test_validation_checks.py` :: missing mandatory action corrected, no GenAI output still applies the rules, compensation checks |
| Policy | `unit/test_validation_checks.py` :: outdated citation, lower-precedence source warned; `unit/test_versioning.py` (8 tests: supersession, late older version, expiry); `integration/test_validation_and_review.py` :: policy update flags affected complaints; `unit/test_sample_documents.py` :: every rule's policy reference exists |
| Hallucination | `unit/test_validation_checks.py` :: invented facts flagged, derived amount traceable, unsupported refund promise, conditional wording is not a promise |
| Prompt injection | `unit/test_complaint_intake.py` :: injection detected (3 variants); `unit/test_genai_contract.py` :: untrusted text cannot close prompt tags; `integration/test_analysis_pipeline.py` :: injected tags neutralised; `security/test_adversarial.py` :: injection treated as content, malicious document quarantined |
| Duplicate | `integration/test_complaints_api.py` :: exact duplicate rejected; `integration/test_validation_and_review.py` :: near-duplicate linked; `unit/test_complaint_intake.py` :: duplicate hash ignores case and punctuation |
| Missing information | `unit/test_complaint_intake.py` :: too-short descriptions rejected, missing order warned; `integration/test_evaluation_pack.py` (too-short complaint rejected at import) |
| Multi-issue | `unit/test_rule_engine.py` :: multi-issue routing; hold-out multi-issue cases in `make evaluate` |
| Hidden-data readiness | `integration/test_evaluation_pack.py` :: evaluator pack imported and evaluated without code change, hold-out pack meets the minimum; `integration/test_taxonomy_api.py` :: category added at runtime; `unit/test_rule_engine.py` :: brand-new category uses the fallback department; `unit/test_genai_contract.py` :: schema follows the taxonomy |
| Boundary | `unit/test_chunking.py` :: long sections split under the limit, huge paragraph; `unit/test_validation.py` :: oversized and empty files; `unit/test_sla.py` :: at-risk and breach thresholds (6 cases); `unit/test_validation_checks.py` :: compensation cap; `integration/test_validation_and_review.py` :: escalation level out of range; `unit/test_complaint_intake.py` :: business days skip weekends, amounts vs reference numbers |
| Security | `security/test_adversarial.py` (26 tests), `integration/test_auth_api.py` (8), `unit/test_clerk_verifier.py` (6), `integration/test_clerk_webhook.py` (2); see `documentation/security_testing_report.md` |

Also covered: SLA tracking (`unit/test_sla.py`), analytics, trends and exports
(`integration/test_analytics.py`, `unit/test_report_export.py`), and configuration integrity
(`unit/test_complaint_intake.py` :: no YAML value truncated).

## Running

```bash
make infra            # PostgreSQL and Redis (tests use the separate supportnova_test database)
make test             # all backend tests
uv run pytest tests/security -v
make lint             # static checks, backend and frontend
pnpm --dir web build  # production build of the web app
```
