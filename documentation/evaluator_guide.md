# Evaluator Guide

How to test SupportNova against the SRS evaluation challenges (section 1.8) without changing
the application's architecture. The deployed application is at
<https://supportnova-volthaven.vercel.app> (staff console: `/dashboard`); evaluator credentials are in the submission form.
Architecture diagrams: [documentation/diagrams/](diagrams/).

## 1. Hidden complaint dataset

Put the complaints in a folder with a `complaints.jsonl` file, one JSON object per line:

```json
{"dataset_id": "EV-001", "customer_ref": "CUST-800001", "order_ref": null,
 "created_at": "2026-09-20T10:00:00", "channel": "email",
 "title": "Charger sparked", "description": "...", "requested_resolution": null,
 "expected": {"category": "SAFETY", "acceptable_categories": ["SAFETY"]}}
```

`customer_ref`, `order_ref`, `channel`, `requested_resolution` and `expected` are optional
(`customers.csv` and `orders.csv` in the sample format can be added for order facts). Then:

```bash
uv run python -m comparison_engine.evaluate path/to/pack                # GenAI + Python, timed
uv run python -m comparison_engine.evaluate path/to/pack --python-only  # Pipeline 2 only
```

Complaints go through the normal intake path (`source="evaluation"`), then through both
pipelines exactly as in production. The CSV in `reports/` has the SRS comparison columns and
the latency of each complaint; the summary JSON has accuracy (if labels were given),
GenAI/Python agreement, verification outcomes and latency against the 20-second target.

Single complaints can also be entered in the web app (**Submit a complaint**, or
**Complaint queue → Log a complaint**).

## 2. Hidden policy update

1. **Knowledge base → Upload document** with the revised policy (same Document ID, higher
   version), **Activate when processed** ticked.
2. When processing finishes, the new version becomes *Active*, the old one *Superseded*
   (kept for traceability, never retrieved again).
3. Every open complaint whose latest analysis used the old version is flagged for review
   with the reason "DEL-POL-04 v1.0 was superseded by v2.0" (see **Manual review**).
4. On such a complaint, **Re-run analysis** grounds the response in the new version;
   Pipeline 2 fails any citation of the superseded version.
5. If the update changes an escalation threshold, edit the matching rule in
   **Rule matrix** (the rules are the executable form of the policy).

An *older* version uploaded after a newer one is recorded as superseded and never replaces
the active version.

## 3. Hidden complaint category

**Taxonomy & SLAs → Complaint categories → add** the category and its subcategories. The
GenAI JSON schema is generated from the database, so the next analysis can use the new codes
immediately. Until a resolution rule exists, the category's department comes from
`routing_rules/routing.yaml` (`category_default_department`, or the fallback department);
add a rule in **Rule matrix** for its routing, priority and actions. The Python keyword
classifier does not know the new category and abstains (the category check is skipped
rather than wrong); patterns can be added in `config/classification.yaml`.

## 4. The traps

| Challenge | Where to see it |
|---|---|
| Sentiment-urgency trap | Calm safety complaint → P0, escalation 5 (rule ESC-001/ESC-003); furious minor complaint → P2/P3 with a note that tone does not drive urgency (validation check "urgency") |
| Escalation trap | Python applies every escalation rule independently; the "escalation" check fails and Python enforces the level when the GenAI misses it |
| Prompt injection | Detected as a risk signal, quoted in `suspicious_instructions`, escalated for supervisor review (ESC-015); an answer that obeys it fails the injection check |
| Unsupported promise | Promise and compensation checks; complaint goes to manual review |
| Contradictory policy | `FAQ-GEN-01` contradicts `REF-POL-01`; precedence in `config/knowledge_base.yaml` (policy over FAQ); citing the lower-precedence source is flagged |
| Missing information | `missing_information` and `clarification_questions` in the output; intake rejects descriptions too short to act on |
| Multi-issue | Primary and secondary issues; the most severe department is primary, the others supporting (`routing_rules/routing.yaml`) |
| Repeat complaint | Named previous complaint, near-duplicate (fuzzy text ≥ 88%) or reworded repeat (embedding similarity ≥ 0.80) is linked; repeat rules escalate |

The test suite contains each of these (`tests/unit/test_rule_engine.py`,
`tests/unit/test_validation_checks.py`, `tests/security/test_adversarial.py`).

## 5. Live modification tasks

Changes in the web app take effect on the next analysis/validation. Changes to YAML files
need the API and worker restarted (`make api`, `make worker`).

| Task | How | Where |
|---|---|---|
| Add a complaint category | Taxonomy & SLAs → add category and subcategories | Database (no code) |
| Add a routing rule | Rule matrix → New rule (category, condition, department) | Database |
| Change priority logic | Edit the rule's priority/urgency in Rule matrix; department precedence in `routing_rules/routing.yaml` | Database / YAML |
| Add a department | Taxonomy & SLAs → Departments → add; add it to `severity_order` in `routing_rules/routing.yaml` to set its precedence | Database / YAML |
| Change an escalation threshold | Rule matrix → edit the escalation rule's condition, e.g. ESC-012 `order_amount > 1000` → `> 800` | Database |
| Modify an SLA | Taxonomy & SLAs → SLA targets | Database |
| Change the JSON schema | Add the field to `schemas/complaint_analysis.py` (Pydantic); the JSON schema and its fingerprint are generated from it; add a check in `genai_pipeline/validation.py` if needed | Code |
| Add a validation rule | Add a check function in `python_validation/checks.py` and list it in `validate()`; simple limits (compensation caps, never-allowed actions, score weights) are in `config/validation.yaml` | Code / YAML |
| Add a dashboard filter | Add a field to `Filters` in `src/analytics/filters.py`, a query parameter in `analytics_filters()` (`src/api/routes/analytics.py`) and a control in `web/src/components/analytics/filter-bar.tsx`, then `make openapi` | Code |

## 6. Deliberate defects

`make test` (436 tests) and `make lint` (ruff, mypy --strict, eslint, tsc) catch defects in:

| Area | Tests that fail |
|---|---|
| Python validation | `tests/unit/test_validation_checks.py`, `tests/integration/test_validation_and_review.py` |
| Routing logic | `tests/unit/test_rule_engine.py`, `tests/unit/test_dataset.py` (every dataset label must agree with the rules) |
| Prompt template | `tests/integration/test_analysis_pipeline.py` (context, escaping, taxonomy in the prompt), `tests/unit/test_genai_contract.py` |
| JSON parsing | `tests/unit/test_genai_contract.py`, retry and invalid-output tests in `test_analysis_pipeline.py` |
| Schema validation | `tests/unit/test_genai_contract.py` (schema matches the vocabulary and taxonomy) |

At run time, invalid GenAI output is never used: it is retried once with the errors, then the
complaint goes to manual review with the raw output kept as evidence.

## 7. Useful commands

```bash
make test               # all backend tests
make report-baseline    # Python-only accuracy on the 531 dataset complaints
make evaluate-python    # Python-only accuracy on the 108 hold-out complaints
make evaluate           # GenAI + Python + latency on the hold-out (needs an API key)
make reports            # Complaint Intelligence Report (PDF, Excel, CSV)
make sla-scan           # SLA risk scan now
```
