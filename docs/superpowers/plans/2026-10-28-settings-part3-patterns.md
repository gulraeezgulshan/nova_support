# Settings Part 3 (Text patterns) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Risk-signal word lists, classifier phrase lists and promise wording become admin settings on a new Settings → Patterns page, with a test panel (pasted text and the 536 labelled complaints) and a Recompute signals button.

**Architecture:** A `patterns` group in the run-time settings (defaults from the three YAML files). The detector, classifier and promise checker compile from `app_settings.runtime().patterns`, cached by content. A small `pattern_lab` package runs the text test and dataset check by overriding the run-time settings inside a separate, time-limited process; dedicated `/settings/patterns` endpoints save, test and recompute.

**Tech Stack:** FastAPI, Pydantic 2, SQLAlchemy 2, Celery, pytest, `multiprocessing` (spawn); Next.js 16, TanStack Query, generated @hey-api client (`make openapi`).

**Spec:** `docs/superpowers/specs/2026-10-28-settings-part3-patterns-design.md`

## Global Constraints

- Entry = `{text, mode: "phrase" | "regex"}`; text 1–300 characters after trimming. Phrase → `re.escape`; in promise lists a phrase gets `\b…\b`. Signals and classifier keep the `(?<!\w)(?:…)(?!\w)` wrapper and IGNORECASE.
- Limits: `signals` exactly the 14 names of `config/detectors.yaml`, 1–80 entries each; `classifier` weight 1–3, 0–40 entries per subcategory; `promises.commitment` / `conditional` 1–30; `promises.kinds` exactly `refund, replacement, compensation, policy_exception`, 1–30 each; `promises.deadline` one regex with exactly 3 capturing groups.
- Every regex compiles; no nested unbounded quantifier (group followed by `+`, `*`, `{n,}` containing `+`, `*`, `{n,}`); bounded repeats like `(?:\w+ ){0,4}` allowed; no duplicate entry in a list.
- 422 texts: `<where>, entry <n>: regex does not compile: <re error>`, `<where>, entry <n>: may be very slow on some texts`, `<where>: entry <n> is listed twice`, `Classifier <CAT>/<SUB>: subcategory does not exist.`, `Deadline must keep its 3 groups (amount, business/working, unit).`, `Patterns are too slow: <where>`, `Testing took too long: a pattern may be very slow.` `<where>` is the signal name, `Classifier CAT/SUB`, `Promises commitment|conditional`, or `Promises kind <kind>`.
- Time limits (measured from the child being ready, not process start): save stress test 2 s, text test 2 s, dataset check 30 s. Text 1–5 000 characters.
- Endpoints admin-only: `GET/PUT /settings/patterns`, `POST /settings/patterns/test`, `POST /settings/patterns/dataset-check`, `POST /settings/patterns/recompute-signals` (202). Audit: `settings.updated` with `audit_group="patterns"`; `patterns.signals_recomputed` `{changed, total}`.
- Commit after each task, no `Co-Authored-By` line. Never commit `documentation/architecture.drawio`.

## Review Focus

1. A stored patterns group that later fails validation (e.g. a signal removed from `detectors.yaml`) must fall back to defaults for that group only, never break every settings read — Task 1 test `test_bad_patterns_group_resets_only_that_group`.
2. Two concurrent API requests must never see each other's draft: drafts only run inside the child process — Task 4 test `test_draft_does_not_leak_into_runtime`.
3. A phrase with regex characters (`50% off?`, `a.b`) matches literally in every reader — Task 2 test `test_phrase_entries_match_literally`.
4. Saving patterns must leave email/AI/validation/access groups untouched — Task 4 test `test_save_keeps_other_groups`.
5. A catastrophic regex that slips past the static check (e.g. `(a|aa)+`) is stopped by the time limit, not by hanging the API — Task 3 test `test_run_limited_stops_slow_work` and Task 4 `test_slow_pattern_refused_on_save`.

---

### Task 1: Patterns settings model and defaults

**Files:**
- Create: `app_settings/patterns.py`
- Modify: `app_settings/model.py`, `app_settings/defaults.py`
- Test: `tests/unit/test_pattern_settings.py`

**Interfaces:**
- Produces (`app_settings/patterns.py`): `PROMISE_KINDS: tuple[str, ...]`; `entry_source(entry: PatternEntry, *, bounded: bool = False) -> str`; `joined(entries: Sequence[PatternEntry], *, bounded: bool = False) -> str` (`"|".join(f"(?:{src})")`); `regex_problem(text: str) -> str | None` (compile error text or `"may be very slow on some texts"`); `signal_descriptions() -> dict[str, str]`; `supported_by() -> dict[str, list[str]]` (from `validation_config()["promises"]["kinds"]`).
- Produces (`app_settings/model.py`): `PatternEntry(text, mode)`, `WeightedEntry(PatternEntry + weight)`, `PromisePatterns(commitment, conditional, kinds, deadline)`, `PatternSettings(signals, classifier, promises)`, `RuntimeSettings.patterns: PatternSettings`.

- [ ] **Step 1: Write the failing tests** in `tests/unit/test_pattern_settings.py`:
  - `test_defaults_equal_the_yaml`: 14 signals; `safety_hazard[0] == PatternEntry(text="overheat\\w*", mode="regex")`; `classifier["DELIVERY"]["LOST_PARCEL"][0].weight == 3`; `len(promises.commitment) == 1` and its text equals the YAML `commitment`; `promises.deadline` equals the YAML `deadline`; every entry is `mode="regex"`.
  - `test_limits_refused` (parametrized, like Part 2's `_set/_drop`): regex `"(unclosed"`; `"(a+)+"`; `"(\\w+\\s?)*"`; text of 301 characters; blank text; duplicate entry; signal list emptied; 81 entries; unknown signal key; missing signal key; weight 0 and 4; 41 classifier entries; kind `cash` added; kind `refund` dropped; empty `commitment`; deadline `"within (\\d+) days"` (1 group).
  - `test_bounded_repeat_allowed`: `regex_problem("arriv\\w* (?:\\w+ ){0,4}late") is None`.
  - `test_error_names_the_place`: injury entry 4 = `"(x"` → message contains `"injury, entry 4: regex does not compile"`.
  - `test_entry_source`: phrase `"a.b"` → `"a\\.b"`; bounded phrase `"money back"` → `r"\bmoney\ back\b"`; regex passes through.
  - `test_bad_patterns_group_resets_only_that_group`: `load({"patterns": {"signals": {"injury": []}}, "email": {"mailbox_check_seconds": 120}})` → patterns equal defaults, email 120.
- [ ] **Step 2: Run** `uv run pytest tests/unit/test_pattern_settings.py -q` — Expected: FAIL (import errors).
- [ ] **Step 3: Implement.** Nested-quantifier check: scan the regex skipping escapes and `[...]` classes, keep a stack of groups flagged "contains unbounded quantifier"; on `)` followed by `+`, `*` or `{n,}` with the flag set → problem; propagate the flag to the parent. `PatternSettings` model validator does all named checks (names from `known_signals()`, `PROMISE_KINDS`, `re.compile(deadline).groups == 3`). Defaults: `_pattern_defaults()` in `defaults.py` reads the three YAMLs (classification `[weight, regex]` pairs → `WeightedEntry`).
- [ ] **Step 4: Run** the new tests plus `uv run pytest tests/unit -q` — Expected: all PASS.
- [ ] **Step 5: Commit** `feat(settings): text patterns in run-time settings`.

### Task 2: Readers compile from the settings

**Files:**
- Modify: `complaint_processing/detectors.py`, `python_validation/classifier.py`, `hallucination_checks/promises.py`, `support_chat/intake.py`
- Test: `tests/unit/test_pattern_readers.py`

**Interfaces:**
- Consumes: Task 1 `entry_source`, `joined`, `RuntimeSettings.patterns`.
- Produces: `detect_signals(text)`, `classify(...)`, `find_promises(text)`, `deadline_pattern()` unchanged signatures, now reading `app_settings.runtime().patterns`; `promises.sentence_checks(text) -> list[SentenceCheck]` with `SentenceCheck(sentence: str, commitment: bool, conditional: bool, kinds: list[str])`.

- [ ] **Step 1: Write the failing tests** (helper `_with_patterns(change)` overriding a copy of the defaults):
  - `test_added_signal_phrase_fires`: phrase `"caught fire"` added to `safety_hazard` → `detect_signals("It caught fire overnight")["safety_hazard"] == ["caught fire"]`; with defaults it does not include `"caught fire"`.
  - `test_phrase_entries_match_literally`: phrase `"a.b"` on `legal_threat` fires on "a.b" not on "axb"; promise kind `compensation` phrase `"50% off?"` found in "We will give you 50% off? now." as kind `compensation`.
  - `test_classifier_uses_saved_phrases`: weight-3 phrase `"zebra parcel"` on `DELIVERY/LOST_PARCEL` → `classify("my zebra parcel", {}, taxonomy).primary.subcategory == "LOST_PARCEL"`.
  - `test_deadline_from_settings`: deadline changed to `"\\b(?:in) (\\d+) (business )?(fortnights?)\\b"` → `deadline_pattern().search("in 2 fortnights")` matches.
  - `test_sentence_checks`: "We will refund you. If eligible, we will refund you." → first `commitment=True, conditional=False, kinds=["refund"]`, second `conditional=True`.
  - `test_change_applies_without_restart`: two overrides in a row give different results (cache keyed by content).
- [ ] **Step 2: Run** `uv run pytest tests/unit/test_pattern_readers.py -q` — Expected: FAIL.
- [ ] **Step 3: Implement.** Each reader builds a hashable key from the settings (tuples of `(name, joined source)` / `(category, subcategory, ((weight, source), ...))` / promise sources) and passes it to an `@lru_cache(maxsize=8)` compile function. `supported_by` stays from `validation_config()`. Remove `signal_lexicons` use from the detector (leave the function in `domain.py`; `known_signals()` still reads names from YAML).
- [ ] **Step 4: Run** `uv run pytest -q` (whole suite, including `test_dataset.py`, `test_validation_checks.py`, `test_chat_intake.py`) — Expected: all PASS.
- [ ] **Step 5: Commit** `feat(patterns): detector, classifier and promise checks read the settings`.

### Task 3: Pattern lab (limited runs, text test, dataset check)

**Files:**
- Create: `pattern_lab/__init__.py`, `pattern_lab/sandbox.py`, `pattern_lab/lab.py`, `pattern_lab/models.py`, `sample_complaints/evaluate.py`
- Modify: `tests/unit/test_dataset.py` (import `facts_for` and loaders from `sample_complaints.evaluate`)
- Test: `tests/unit/test_pattern_lab.py`

**Interfaces:**
- Consumes: Task 2 readers, `sentence_checks`.
- Produces:
  - `pattern_lab.sandbox.run_limited(target: Callable[..., T], args: tuple[Any, ...], seconds: float) -> T`; raises `TooSlowError`. Spawn context; the child sends `"ready"` after imports, then the result; the limit counts from `"ready"` (start allowance 30 s); on timeout terminate the child.
  - `pattern_lab.lab.try_text(settings: dict, draft: dict, text: str, taxonomy: dict[str, list[str]]) -> dict` (a `TextTestOut` dump) and `dataset_check(settings: dict, draft: dict, taxonomy) -> dict` (a `DatasetCheckOut` dump) and `stress_check(draft: dict) -> None` (runs every list on stress strings). Arguments are plain dicts so they pickle; inside, `app_settings.override(RuntimeSettings.model_validate(settings) with patterns = saved or draft)` per side.
  - `pattern_lab.models`: `TextSide{signals: dict[str, list[str]], classification: ClassificationOut{status, primary: str | None, candidates: list[CandidateOut{category, subcategory, score}]}, sentences: list[SentenceOut]}`, `TextTestOut{saved, draft}`, `SignalDelta{signal, saved: int, draft: int, gained: list[DatasetHit], lost: list[DatasetHit]}`, `DatasetHit{dataset_id, phrases: list[str]}`, `DatasetCheckOut{total, signals: list[SignalDelta], classifier: ClassifierCompare{saved_correct, draft_correct, saved_confident, draft_confident, right_to_wrong: list[str], wrong_to_right: list[str]}, escalation: Compare{saved, draft, total}, urgency: Compare, prompt_injection: InjectionCompare{saved: Hits{true_positive, false_positive}, draft: Hits}}`.
  - `sample_complaints.evaluate`: `load_dataset() -> Dataset(complaints, orders, customers)`, `record_text(record) -> str`, `prior_for(record, accepted) -> list`, `facts_for(record, orders, customers, prior, signals) -> dict`, `yaml_taxonomy() -> dict[str, list[str]]` (from `config/taxonomy.yaml`).

- [ ] **Step 1: Write the failing tests:**
  - `test_run_limited_returns_result`: `run_limited(operator.add, (2, 3), 5) == 5`.
  - `test_run_limited_stops_slow_work`: target `re.fullmatch("(a|aa)+$", "a"*40 + "b")` (module-level helper), limit 1 s → `TooSlowError` within 35 s wall time.
  - `test_try_text_shows_draft_difference`: draft adds `"caught fire"` → `draft.signals["safety_hazard"]` contains it, `saved.signals` lacks it.
  - `test_dataset_check_defaults_are_equal`: draft = saved → every `SignalDelta.saved == draft`, `gained == lost == []`, `classifier.saved_correct == draft_correct`, `total == 536`.
  - `test_dataset_check_detects_gain`: draft adds phrase `"order"` to `legal_threat` → its `draft > saved` and `gained` non-empty, at most 10.
  - `test_defaults_pass_stress_check`: `run_limited(stress_check, (defaults().patterns.model_dump(),), 2)` returns without error.
  - `test_stress_check_refuses_slow`: `stress_check` inside `run_limited` with a draft containing `(a|aa)+` → `TooSlowError`.
  - `test_dataset.py` still passes after the move.
- [ ] **Step 2: Run** `uv run pytest tests/unit/test_pattern_lab.py -q` — Expected: FAIL.
- [ ] **Step 3: Implement.** Classifier correct = primary category equals `expected.category` or is in `acceptable_categories`; escalation/urgency over accepted complaints with `read_default_matrix()` and expected issues, as `test_dataset.py` does; prompt injection compares `bool(signals.get("prompt_injection"))` with `expected.prompt_injection`. Stress strings (each ~20 000 characters, each ending so a match fails late): `"a" * 20_000 + "b"`, `"a " * 10_000 + "b"`, `"a!" * 10_000`, and the sentence `"The parcel was late and the charger got very hot, we will refund you. "` repeated to 20 000 characters.
- [ ] **Step 4: Run** `uv run pytest tests/unit -q` — Expected: all PASS.
- [ ] **Step 5: Commit** `feat(patterns): pattern lab with time-limited text and dataset checks`.

### Task 4: Patterns API and recompute task

**Files:**
- Create: `src/api/routes/patterns.py`
- Modify: `src/api/schemas.py`, `src/api/main.py` (or wherever routers are included), `app_settings/tasks.py`, `web/openapi.json` + generated client (`make openapi`)
- Test: `tests/integration/test_patterns_api.py`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces: schemas `PatternsOut{patterns, defaults: PatternSettings, version, updated_at, updated_by, signal_descriptions: dict[str,str], supported_by: dict[str,list[str]], last_recompute: RecomputeOut | None}`, `RecomputeOut{at, changed, total}`, `PatternsUpdate{version, patterns}`, `PatternTestIn{draft: PatternSettings, text: str (1–5000)}`, `DatasetCheckIn{draft}`, `RecomputeQueuedOut{queued: bool}`; operation ids `readPatterns`, `updatePatterns`, `testPatterns`, `checkPatternsOnDataset`, `recomputeSignals`; Celery task `app_settings.tasks.recompute_signals(actor_id: str | None) -> dict[str, int]`.

- [ ] **Step 1: Write the failing tests:**
  - `test_admin_reads_patterns`: 200, 14 descriptions, `supported_by["refund"]` contains `ISSUE_FULL_REFUND`, `last_recompute is None`.
  - `test_save_and_apply`: PUT with `caught fire` added → 200, version +1; `detect_signals` after `app_settings.reset_cache()` fires on it.
  - `test_save_keeps_other_groups`: stored email change survives a patterns save.
  - `test_unknown_subcategory_refused`: `classifier["DELIVERY"]["FOO"]` → 422 `Classifier DELIVERY/FOO: subcategory does not exist.`
  - `test_stale_version_conflict` → 409.
  - `test_slow_pattern_refused_on_save`: entry `(a|aa)+` → 422 starting `Patterns are too slow`.
  - `test_text_test_endpoint`: 200, draft differs; text of 5 001 characters → 422.
  - `test_dataset_check_endpoint`: 200, `total == 536`.
  - `test_draft_does_not_leak_into_runtime`: after a test call with a draft, `app_settings.runtime().patterns` equals the stored patterns.
  - `test_recompute_task`: a stored complaint whose `signals` lack `safety_hazard` but text says "caught fire"; save the phrase; run `recompute_signals(None)` eagerly → complaint updated; audit `patterns.signals_recomputed` `{changed: ≥1, total}`; GET shows `last_recompute`.
  - `test_staff_forbidden`: agent → 403 on all five endpoints.
- [ ] **Step 2: Run** `uv run pytest tests/integration/test_patterns_api.py -q` — Expected: FAIL.
- [ ] **Step 3: Implement.** PUT: taxonomy check (query `Category`/`Subcategory`, as Part 2's `_check_validation_codes`), then `run_limited(stress_check, (draft,), 2)`, then `app_settings.save(..., action="settings.updated", audit_group="patterns")` with the loaded settings `model_copy(update={"patterns": ...})`. Test/dataset: active taxonomy from the database, `run_limited(try_text|dataset_check, (runtime().model_dump(), draft.model_dump(), ...), 2|30)`; `TooSlowError` → 422 `Testing took too long: a pattern may be very slow.` Recompute: `.delay(str(actor.id))`, 202. The task wraps `complaint_processing.recompute_signals.recompute()` and writes `record_sync(..., "patterns.signals_recomputed", "settings", "patterns", after={...})`. Then `make openapi`.
- [ ] **Step 4: Run** `make lint && make test` — Expected: clean, all PASS.
- [ ] **Step 5: Commit** `feat(api): patterns settings, test, dataset check and recompute endpoints`.

### Task 5: Patterns page

**Files:**
- Create: `web/src/app/(app)/settings/patterns/page.tsx`, `web/src/components/settings/patterns-manager.tsx`, `web/src/components/settings/pattern-list.tsx`, `web/src/components/settings/pattern-test-panel.tsx`
- Modify: `web/src/components/app-sidebar.tsx` (entry "Patterns", `href: "/settings/patterns"`, `page: "settings"`, after "Settings")

**Interfaces:**
- Consumes: Task 4 operations; `Field` from `fields.tsx`.
- Produces: `PatternList({entries, defaults, weighted?, onChange})` — rows: text input (monospace), Phrase/Regex select, weight 1–3 when `weighted`, remove; Add; "Default: N entries · Reset".

- [ ] **Step 1: Build** the page per spec §4: header "Patterns" with description "Risk-signal words, classifier phrases and promise wording. Test a change before saving; it applies within about 15 seconds."; tabs Risk signals / Classifier / Promises; two-column layout `lg:grid-cols-[1fr_24rem]` with the test panel second (stacks below on narrow screens); Save/Discard footer with version (409 → toast "Someone else changed the settings; reload and try again."); Recompute button + "Last run: …, N of M complaints changed"; classifier tab category/subcategory selects from `listCategoriesOptions()`, empty list text "No phrases: Python never names it."; promise kinds show `supported_by` codes read-only; deadline single monospace input.
- [ ] **Step 2: Verify** `pnpm --dir web typecheck && pnpm --dir web lint && pnpm --dir web build` — Expected: 0 errors.
- [ ] **Step 3: Browser check** (admin signed in, localhost:3000): add phrase "caught fire" to safety_hazard → Try a text "The charger caught fire" → fires in draft only → dataset check shows totals → Save → Reset → Save; page fits at the pane's narrow width without horizontal scroll.
- [ ] **Step 4: Commit** `feat(web): Patterns settings page with test panel`.

### Task 6: Documentation and full check

**Files:** `documentation/user_guide.md` (Patterns section), `documentation/evaluator_guide.md` (row "Add a risk keyword | Settings → Patterns → Risk signals → Save → Recompute signals | Database (no code)"), `documentation/project_report.md` (note in §23 and the risk-signal section: patterns are settings with a test panel).

- [ ] **Step 1:** write the changes.
- [ ] **Step 2:** `make lint && make test` (all pass) and `pnpm --dir web build` (clean).
- [ ] **Step 3:** `git commit -m "docs: patterns settings"`
