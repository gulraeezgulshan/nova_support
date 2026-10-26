# Settings Part 2 (Validation & classifier) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Check weights, compensation limits, never-allowed actions, categories needing an order, escalation action levels, classifier thresholds and signal boosts become admin settings on a new Validation tab.

**Architecture:** A `validation` group in the existing run-time settings (defaults from `config/validation.yaml` and `config/classification.yaml`). `verdict_config()` and the classifier read it via `app_settings.runtime()`; the promise patterns and classifier phrase lists stay in YAML (Part 3).

**Tech Stack:** FastAPI, Pydantic 2, pytest; Next.js 16, generated @hey-api client.

**Spec:** `docs/superpowers/specs/2026-10-27-settings-part2-validation-classifier-design.md`

## Global Constraints

- Limits (spec §1): weights each 1–10 with critical ≥ major ≥ minor; compensation keys exactly `store_credit, shipping_fee_refund, partial_refund, full_refund, replacement, repair, voucher`; `requires_any` 1–20 known action codes; `max_pct_of_order` 0–100 or null; `max_amount` 0–10000 or null; `never_allowed_actions` 0–60 known, unique action codes; `orders_required_for` 0–30 unique category codes; `escalation_action_levels` keys exactly `ESCALATE_TO_SUPERVISOR, ESCALATE_TO_MANAGER, ESCALATE_TO_SPECIALIST, ESCALATE_TO_COMPLIANCE, ESCALATE_TO_CRITICAL_MANAGEMENT`, values 1–5; `classifier_confident`, `classifier_secondary` 1–10; `signal_boosts` 0–14 entries keyed by a risk-signal name from `config/detectors.yaml`, weight 1–5.
- "Known action codes" = keys of `src.core.domain.actions()` (from `config/actions.yaml`).
- `verified_min_score` / `always_review_escalation_level` stay in `operations`; no stored data moves.
- `PUT /settings`: `validation` optional (left out = keep stored). 422 texts: `Needs an order: category <CODE> does not exist.`; `Signal boost <signal>: category <CAT> does not exist.`; `Signal boost <signal>: subcategory <SUB> is not in category <CAT>.`
- Unknown or inactive taxonomy codes in stored values never raise at read time.
- UI warning when unticking a never-allowed action: "This removes a safety guard: the AI may then propose it."
- Commits: one per task, no `Co-Authored-By` line.

## Review Focus

- A category in `orders_required_for` is later removed from Taxonomy → validation must keep running → Task 3 test with a stored unknown category.
- A signal boost points at a subcategory that is later deactivated → classification must skip it → Task 3 test.
- An admin unticks every never-allowed action → checks run, nothing removed → Task 3 test.
- `max_amount: null` ("no limit") on store credit → any amount passes the cap part of the compensation check → Task 3 test.
- A compensation entry saved with an unknown or duplicated action code → refused before saving → Task 1 test.

---

### Task 1: The `validation` settings group

**Files:**
- Modify: `app_settings/model.py`, `app_settings/defaults.py`
- Test: `tests/unit/test_validation_settings.py`

**Interfaces:**
- Produces (in `app_settings/model.py`):
  - `COMPENSATION_TYPES: tuple[str, ...]` and `ESCALATION_ACTIONS: tuple[str, ...]` (values from Global Constraints)
  - `ScoreWeights(_Group)`: `critical: int`, `major: int`, `minor: int`
  - `CompensationLimit(_Group)`: `requires_any: list[str]`, `max_pct_of_order: float | None = None`, `max_amount: float | None = None`
  - `SignalBoost(_Group)`: `category: str`, `subcategory: str`, `weight: int`
  - `ValidationSettings(_Group)`: `score_weights: ScoreWeights`, `compensation: dict[str, CompensationLimit]`, `never_allowed_actions: list[str]`, `orders_required_for: list[str]`, `escalation_action_levels: dict[str, int]`, `classifier_confident: int`, `classifier_secondary: int`, `signal_boosts: dict[str, SignalBoost]`; a `model_validator(mode="after")` enforces the Global Constraints (action codes and signal names checked with local imports: `src.core.domain.actions`, and the top-level keys of `config/detectors.yaml` → `signals`).
  - `RuntimeSettings.validation: ValidationSettings`
- `defaults()` fills `validation` from `validation_config()` (YAML: `score_weights`, `compensation`, `never_allowed_actions`, `orders_required_for`, `escalation_action_levels`) and `config/classification.yaml` (`thresholds.confident`, `thresholds.secondary`, `signal_boosts` `[cat, sub, weight]` → `SignalBoost`).

- [ ] **Step 1: Write failing tests** (`tests/unit/test_validation_settings.py`):

```python
def test_defaults_equal_the_yaml():
    v = app_settings.defaults().validation
    assert v.score_weights.model_dump() == {"critical": 5, "major": 3, "minor": 1}
    assert v.compensation["store_credit"].max_amount == 50
    assert v.compensation["store_credit"].max_pct_of_order == 10
    assert v.compensation["full_refund"].max_amount is None
    assert (
        "PROMISE_CASH_COMPENSATION" in v.never_allowed_actions and len(v.never_allowed_actions) == 7
    )
    assert v.orders_required_for == [
        "DELIVERY",
        "PRODUCT_DEFECT",
        "REFUND",
        "RETURNS_REPLACEMENT",
        "WARRANTY",
    ]
    assert v.escalation_action_levels["ESCALATE_TO_SUPERVISOR"] == 1
    assert (v.classifier_confident, v.classifier_secondary) == (3, 3)
    assert v.signal_boosts["safety_hazard"].model_dump() == {
        "category": "SAFETY",
        "subcategory": "OVERHEATING_BATTERY",
        "weight": 3,
    }
```
Plus parametrized refusals (each builds `ValidationSettings.model_validate(defaults_dump | change)` and expects `ValidationError`): weight 0 / 11; critical 2 < major 3; a missing compensation key; an extra compensation key `"cash"`; `requires_any` empty; `requires_any` with `"NOT_AN_ACTION"`; `requires_any` with a duplicate code; `max_pct_of_order` 101; `max_amount` -1; never-allowed with an unknown code or a duplicate; escalation level 0 / 6; a missing escalation key; thresholds 0 / 11; boost weight 6; boost keyed `"not_a_signal"`; 15 boosts. And `test_bad_validation_group_resets_only_that_group` (stored `{"validation": {"classifier_confident": 0}, "email": {"mailbox_check_seconds": 120}}` → validation defaults, e-mail 120).

- [ ] **Step 2: Run** `uv run pytest tests/unit/test_validation_settings.py -q` → FAIL (no `validation` attribute).
- [ ] **Step 3: Implement** the models, constants, validator and defaults. Keep `PUT /settings` working by carrying the stored group (`validation=payload.validation or stored.validation` arrives in Task 2; in this task pass `validation=stored.validation` in `update_settings`).
- [ ] **Step 4: Run** the new tests plus `tests/unit/test_kb_ai_settings.py tests/integration/test_settings_api.py tests/integration/test_app_settings_store.py` → PASS; full `uv run pytest -q` → PASS.
- [ ] **Step 5: Lint and commit** — `uv run ruff check . && uv run mypy .` then
  `git commit -m "feat(settings): validation and classifier values in run-time settings"`

---

### Task 2: Save the group, with taxonomy and signal checks

**Files:**
- Modify: `src/api/schemas.py` (`SettingsUpdate.validation: ValidationSettings | None = None`; `SettingsOut.risk_signals: list[str]` = the signal names from `config/detectors.yaml`, for the boost picker), `src/api/routes/settings.py`
- Test: `tests/integration/test_settings_api.py`

**Interfaces:**
- Consumes: Task 1 models.
- Produces: `update_settings` saves `payload.validation or stored.validation`; before saving, when `payload.validation` is given, checks codes against the `categories` / `subcategories` tables (all rows, active or not) and raises 422 with the Global Constraints texts (all problems joined with a space).

- [ ] **Step 1: Write failing tests:** `test_admin_saves_validation_values` (store credit max 75 saved and read back; `defaults.validation.compensation.store_credit.max_amount == 50`); `test_unknown_category_needing_an_order_is_refused` (`"FOO"` → 422, text "Needs an order: category FOO does not exist."); `test_boost_subcategory_outside_category_is_refused` (safety_hazard → category `BILLING`, subcategory `OVERHEATING_BATTERY` → 422 with the exact text); `test_boost_unknown_category_is_refused`; `test_validation_left_out_keeps_stored_values` (save store credit 75, then a PUT without `validation` → still 75). Extend `body()` to include `validation`. Also assert `GET /settings` returns `risk_signals` containing `safety_hazard` and `prompt_injection` (14 names).
- [ ] **Step 2: Run** `uv run pytest tests/integration/test_settings_api.py -q` → new tests FAIL.
- [ ] **Step 3: Implement** the schema field and `_check_validation_codes(db, v: ValidationSettings) -> None`.
- [ ] **Step 4: Run** the file, full suite, then `make openapi` and keep the web compiling (`toForm` passes `validation` through: `validation: s.settings.validation`); `pnpm --dir web typecheck` → 0.
- [ ] **Step 5: Commit** `git commit -m "feat(settings): save validation settings with taxonomy checks"`

---

### Task 3: Python's checks and the classifier read the settings

**Files:**
- Modify: `python_validation/checks.py` (`verdict_config`), `python_validation/classifier.py`
- Test: `tests/unit/test_validation_checks.py` (append), `tests/unit/test_classifier_settings.py`

**Interfaces:**
- Consumes: `runtime().validation` (Task 1).
- Produces:
  - `verdict_config() -> dict[str, Any]` returns the same keys as today: `score_weights` (dict), `compensation` (dict of dicts; null limits omitted, so `rule.get(...)` behaves as before), `never_allowed_actions`, `orders_required_for`, `escalation_action_levels` from settings; `verified_min_score`, `always_review_escalation_level` from `operations`; `promises` and any other YAML-only keys from `validation_config()`.
  - `classifier._patterns() -> dict[tuple[str, str], list[_Pattern]]` (`lru_cache`, compiled from YAML); `classify()` reads `confident`, `secondary` and boosts from `runtime().validation` on every call. `_Config`/`_config()` are removed.

- [ ] **Step 1: Write failing tests** (use `app_settings.override(app_settings.load({"validation": {...}}))`; the `vocab`, `rules`, `analysis`, `run`, `check` helpers already in `test_validation_checks.py`):
  - `test_score_weight_from_settings`: an analysis with one major failure; score with major weight 1 > score with the default 3.
  - `test_compensation_cap_from_settings`: store credit USD 60 (the `test_compensation_above_policy_cap` set-up with `amount=60`) fails by default, passes with `max_amount: 75`; with `max_amount: None` and `max_pct_of_order: None` it passes too.
  - `test_never_allowed_from_settings`: an analysis proposing `PROMISE_CASH_COMPENSATION` → removed by default; with that code unticked → not removed; with `never_allowed_actions: []` → `validate()` still returns an outcome.
  - `test_orders_required_from_settings`: delivery complaint without an order → `missing_information` FAIL by default; with DELIVERY removed → not FAIL; with `["GHOST", "DELIVERY"]` stored → no exception.
  - `test_escalation_level_from_settings`: GenAI escalation level 1 with required `ESCALATE_TO_SUPERVISOR` → counted done by default; with supervisor level 2 → required action missing.
  - `tests/unit/test_classifier_settings.py`: `test_confident_threshold_from_settings` (a text scoring exactly 3 for one subcategory → `confident` by default, `tentative` with `classifier_confident: 6`); `test_boost_weight_from_settings` (safety signal score rises by the configured weight); `test_boost_to_inactive_subcategory_is_skipped` (taxonomy without the boost's subcategory → no `signal:` evidence, no error).
- [ ] **Step 2: Run** `uv run pytest tests/unit/test_validation_checks.py tests/unit/test_classifier_settings.py -q` → new tests FAIL.
- [ ] **Step 3: Implement** the reader changes.
- [ ] **Step 4: Run** those files, then the whole suite → PASS (defaults reproduce today's verdicts).
- [ ] **Step 5: Lint and commit** `git commit -m "feat(settings): validation checks and classifier read the settings"`

---

### Task 4: Validation tab on the Settings page

**Files:**
- Modify: `web/src/components/settings/settings-manager.tsx`
- Create: `web/src/components/settings/validation-settings.tsx` (the tab body; props `{ value: ValidationSettings, defaults: ValidationSettings, operations, operationsDefaults, onChange, onOperationsChange, actionCodes: string[], categories: CategoryOut[] }`)

**Interfaces:**
- Consumes: generated `ValidationSettings`, `SettingsOut.defaults.validation`, `SettingsOut.risk_signals` (boost picker), `getVocabularyOptions()` (`actions[].code`) and `listCategoriesOptions()` (categories with subcategories).

- [ ] **Step 1: Implement** per spec §4: sections Verdict, Compensation (no-limit checkbox per limit), Never-allowed actions (checkbox list; unticking a code that is in the defaults shows the Global Constraints warning), Needs an order, Escalation action levels, Classifier (thresholds; boost table with signal select from `risk_signals`, category and subcategory selects filtered by category, weight; add/remove rows). Every field: "Default: X · Reset" (reuse `Field`'s `defaultText`/`onReset`; export `Field` and `NumberInput` from `settings-manager.tsx` or move them to `web/src/components/settings/fields.tsx`). Tab label "Validation", placed after "Knowledge base". `Form` gains `validation: ValidationSettings`.
- [ ] **Step 2: Verify** `pnpm --dir web typecheck && pnpm --dir web lint && pnpm --dir web build` → clean.
- [ ] **Step 3: Browser check** (admin signed in): store credit max 75 → Save → saved; Reset → 50 → Save; untick a never-allowed action → warning shown, Discard. If the pane is signed out, record it and ask the user at the end.
- [ ] **Step 4: Commit** `git commit -m "feat(web): Validation settings tab"`

---

### Task 5: Documentation and full check

**Files:** `documentation/user_guide.md` (Validation row in the Settings table), `documentation/evaluator_guide.md` (row "Change a compensation limit | Settings → Validation → Compensation → Save | Database (no code)"), `documentation/project_report.md` (§23 note: weights, limits and thresholds are settings).

- [ ] **Step 1:** write the changes.
- [ ] **Step 2:** `make lint && make test` (all pass) and `pnpm --dir web build` (clean).
- [ ] **Step 3:** `git commit -m "docs: validation settings"`
