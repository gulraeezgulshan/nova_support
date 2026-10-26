# Settings, Part 2: validation and classifier values on the Settings page

Date: 2026-10-27. Status: design approved in conversation, awaiting spec review.

## Context

Part 2 of four (Part 1, knowledge base & AI, is done and pushed). Agreed in conversation: Part 2
moves the **numbers and lists** of Python's validation and classifier to Settings. The **text
patterns** (promise wording in `config/validation.yaml → promises`, the classifier phrase lists
in `config/classification.yaml → subcategories`) move in **Part 3** together with the detector
word lists, because they need a test-before-save editor.

## Goal

An administrator changes the check weights, compensation limits, never-allowed actions, the
categories that need an order, the escalation action levels, the classifier thresholds and the
signal boosts from a new **Validation** tab, without a redeploy.

## 1. Settings, defaults and limits

New group `validation` in the run-time settings (`app_settings`). Defaults are read from
`config/validation.yaml` and `config/classification.yaml`; nothing stored → today's behaviour.

| Field | Default | Limits |
|---|---|---|
| `score_weights` `{critical, major, minor}` | 5 / 3 / 1 | each 1–10; critical ≥ major ≥ minor |
| `compensation` — one entry per type: `store_credit`, `shipping_fee_refund`, `partial_refund`, `full_refund`, `replacement`, `repair`, `voucher` (exactly these keys; `none` is not a type to limit) | today's entries | `requires_any`: 1–20 action codes, each in `config/actions.yaml`; `max_pct_of_order`: 0–100 or null (no limit); `max_amount`: 0–10000 or null |
| `never_allowed_actions` | the 7 listed today | 0–60 action codes, each in `config/actions.yaml`, unique |
| `orders_required_for` | DELIVERY, PRODUCT_DEFECT, REFUND, RETURNS_REPLACEMENT, WARRANTY | 0–30 category codes, unique; must exist in the live taxonomy (checked on save) |
| `escalation_action_levels` — exactly `ESCALATE_TO_SUPERVISOR`, `ESCALATE_TO_MANAGER`, `ESCALATE_TO_SPECIALIST`, `ESCALATE_TO_COMPLIANCE`, `ESCALATE_TO_CRITICAL_MANAGEMENT` | 1, 2, 3, 4, 5 | each 1–5 |
| `classifier_confident` | 3 | 1–10 |
| `classifier_secondary` | 3 | 1–10 |
| `signal_boosts` — `{signal: {category, subcategory, weight}}` | the 5 today (safety_hazard, injury, privacy_exposure, account_compromise, repeated_repair) | 0–14 entries; `signal` is one of the risk signals in `config/detectors.yaml`; `weight` 1–5; category/subcategory exist in the live taxonomy with the subcategory inside the category (checked on save) |

`verified_min_score` and `always_review_escalation_level` stay in the `operations` group (no
stored data moves); the Validation tab also shows and edits them.

Model checks (always): ranges, the weight order, exact keys for `compensation` and
`escalation_action_levels`, known action codes and signal names, no duplicates. A group with an
invalid stored value falls back to its defaults (Part 1 per-group loading).

## 2. Saving

- `PUT /api/v1/settings` accepts an optional `validation` group (left out = keep stored values),
  like `knowledge_base`.
- Taxonomy checks against the database (active or not) before saving; 422 with the problem, e.g.
  "Needs an order: category FOO does not exist." /
  "Signal boost safety_hazard: subcategory OVERHEATING_BATTERY is not in category BILLING."
- `GET /api/v1/settings` already returns `defaults` (Part 1), now including `validation`.

## 3. Readers

| Value | Reader | Change |
|---|---|---|
| weights, compensation, never-allowed, needs-an-order, escalation levels | `python_validation/checks.py` `verdict_config()` | build these keys from `runtime().validation` (plus the two `operations` values, as today); `promises` still from `validation_config()` (YAML) until Part 3 |
| classifier thresholds and signal boosts | `python_validation/classifier.py` | split `_config()`: compiled phrase patterns stay cached from the YAML; `confident`, `secondary` and `boosts` come from `runtime().validation` on each `classify()` call |

Unknown or inactive taxonomy codes in stored values never raise: `classify()` already skips a
boost whose subcategory is not active; an unknown category in `orders_required_for` simply never
matches.

## 4. Settings page

New tab **Validation** with sections: *Verdict* (weights; verified score and always-review level
bound to the `operations` fields), *Compensation* (table: type, max %, max USD with a "no limit"
option, actions that allow it as a checkbox list), *Never-allowed actions* (checkbox list of all
action codes; unticking one shows "This removes a safety guard: the AI may then propose it."),
*Needs an order* (category checkboxes from the taxonomy), *Escalation action levels* (number per
action), *Classifier* (two thresholds; signal-boost table with signal, category, subcategory
pickers and weight; add/remove rows). Every field shows "Default: X · Reset". Save/Discard as
today.

## 5. Tests

- Defaults equal the YAML values; existing validation and classifier tests unchanged and green.
- Limits refused (each field, weight order, unknown keys/actions/signals, duplicates).
- Save: unknown category → 422; boost subcategory outside its category → 422; unknown signal →
  422; group left out → stored values kept.
- Effects: major weight 3 → 1 raises the score of a run with a major failure; store credit max
  USD 50 → 75 lets a USD 60 offer pass the compensation check; unticking a never-allowed action
  stops it being removed, adding one removes it; removing DELIVERY from needs-an-order stops the
  missing-order failure for a delivery complaint without an order; supervisor level 1 → 2 changes
  when ESCALATE_TO_SUPERVISOR counts as done; confident 3 → 6 makes a borderline complaint
  *tentative*; a boost weight change changes the score; values apply on the next call (no
  restart).
- Web: type check, lint, build; browser: store credit max 75 → Save → Reset → Save; untick a
  never-allowed action → warning shown.

## 6. Documentation

User guide Settings table (Validation row); evaluator guide live-modification row ("Change a
compensation limit | Settings → Validation → Compensation"); project report validation section
note.

## Out of scope

Promise patterns and classifier phrase lists (Part 3); adding compensation types; analytics, shop
and texts (Part 4).
