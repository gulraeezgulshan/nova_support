# Settings, Part 3: text patterns on the Settings page, with test before save

Date: 2026-10-28. Status: design approved in conversation, awaiting spec review.

## Context

Part 3 of four (Parts 1 and 2 are done and pushed). It moves the **text patterns** to the
Settings page: the risk-signal word lists (`config/detectors.yaml`), the classifier phrase lists
(`config/classification.yaml → subcategories`) and the promise wording
(`config/validation.yaml → promises`). Agreed in conversation: entries can be a plain phrase or
a regex; a test panel tries a pasted text and checks the draft against the 536 labelled sample
complaints; saving is never blocked by the dataset result.

## Goal

An administrator edits, tests and saves the patterns from **Settings → Patterns** without a
redeploy, and can recompute the stored complaints' risk signals afterwards.

## 1. Settings, defaults and limits

New group `patterns` in the run-time settings (`app_settings`), stored like the other groups
(only changes from the defaults; per-group fallback to the defaults when a stored value is
invalid). Defaults are read from the three YAML files; nothing stored → today's behaviour.

An **entry** is `{text: str, mode: "phrase" | "regex"}`. A phrase is matched literally
(`re.escape`, spaces kept); a regex as written. Every YAML pattern loads as a regex entry.
Matching keeps today's rules: case-insensitive, word-bounded `(?<!\w)(?:…)(?!\w)` for signals
and classifier, the YAML's own `\b…\b` for promises (a phrase entry in a promise list gets
`\b…\b` around it).

| Part | Shape | What can change | Limits |
|---|---|---|---|
| `signals` | `{signal: [entry]}` | the entries of each of the 14 signals in `detectors.yaml` | exactly those 14 names (they are rule-matrix facts); 1–80 entries each |
| `classifier` | `{CATEGORY: {SUBCATEGORY: [{entry, weight}]}}` | entries and weights of any subcategory | weight 1–3; 0–40 entries per subcategory; category and subcategory must exist in the live taxonomy (checked on save, active or not) |
| `promises.commitment`, `promises.conditional` | `[entry]` | entries | 1–30 each |
| `promises.kinds` | `{kind: [entry]}` | entries of `refund`, `replacement`, `compensation`, `policy_exception` | exactly these kinds; 1–30 entries each; `supported_by` stays in the YAML (read-only on the page) |
| `promises.deadline` | one regex string | the regex | must compile and have exactly 3 capturing groups (amount, "business/working", unit), as `unsupported_promises` reads them |

The promise lists are joined with `|` at match time; as defaults each holds today's single
regex as one entry.

**Safety checks on every entry (model validation, always):** text 1–300 characters after
trimming; a regex must compile; no nested unbounded quantifier (a group followed by `+`, `*` or
`{n,}` that itself contains `+`, `*` or `{n,}`, e.g. `(a+)+`, `(\w+\s?)*`; bounded repeats such
as `(?:\w+ ){0,4}` stay allowed, and every default passes) — refused with "may be very slow on
some texts";
no duplicate entry within a list. On **save** (not on every load) the whole draft is also timed
on stress strings (long runs of letters, spaces and punctuation, 20 000 characters) in a
separate process with a 2-second limit; over the limit → 422 "Patterns are too slow: <first
slow list>".

## 2. Readers

| Reader | Change |
|---|---|
| `complaint_processing/detectors.py` | compile from `runtime().patterns.signals`; cache keyed by the entries (rebuilt only when they change) |
| `python_validation/classifier.py` `_patterns()` | build from `runtime().patterns.classifier`, cached by content (Part 2 already reads thresholds and boosts from settings) |
| `hallucination_checks/promises.py` `_patterns()` and `support_chat/intake.py` `deadline_pattern()` | from `runtime().patterns.promises`, cached by content; `supported_by` still from `validation_config()` |
| `app_settings.model.known_signals()` | unchanged (signal names still from `detectors.yaml`) |

A subcategory with patterns that is inactive or missing in the live taxonomy is skipped, as
today. One shared helper builds an entry's regex source, so the readers, the test endpoints and
the safety check agree.

## 3. API (administrators only)

- `GET /api/v1/settings/patterns` → `{patterns, defaults, version, signal_descriptions,
  supported_by, last_recompute}`; `last_recompute` is `{at, changed, total} | null` (from the
  audit log).
- `PUT /api/v1/settings/patterns` `{version, patterns}` → saves only the `patterns` group (other
  groups untouched), stale version → 409, audit action `settings.updated` with group
  `patterns`. 422 messages name the place, e.g. "injury, entry 4: regex does not compile:
  missing )", "Classifier DELIVERY/FOO: subcategory does not exist.", "Deadline must keep its 3
  groups (amount, business/working, unit)."
- `POST /api/v1/settings/patterns/test` `{draft, text}` (text 1–5 000 characters) → for saved
  and draft: signals fired with matched phrases; classifier status, primary and top 3
  candidates with scores; per sentence: commitment, conditional, promise kinds found.
- `POST /api/v1/settings/patterns/dataset-check` `{draft}` → for saved and draft over
  `sample_complaints/complaints.jsonl`:
  - **signals:** per signal the number of complaints it fires on, and the complaints that
    gained or lost it (dataset id, matched phrases; first 10 each);
  - **classifier:** category equals the label (or is in `acceptable_categories`), confident
    count; complaints right→wrong and wrong→right (first 10 each);
  - **escalation and urgency:** matches with the labelled escalation level and urgency, using
    the default rule matrix (what the labels were written for) and the expected issues, as the
    existing dataset test does;
  - **prompt injection:** detected vs `expected.prompt_injection` (true/false positives).
- `POST /api/v1/settings/patterns/recompute-signals` → 202; a Celery task re-detects the
  signals of every stored complaint with the saved patterns and writes an audit entry
  `patterns.signals_recomputed` `{changed, total}`. It does not re-run the AI analysis.

The test and dataset endpoints validate the draft with the same model checks, then run in a
separate process with a time limit (2 s text, 30 s dataset); over the limit → 422 "Testing took
too long: a pattern may be very slow." The fact-building code of `tests/unit/test_dataset.py`
(`facts_for`) moves to a shared module (`sample_complaints/evaluate.py`) used by both the test
and the dataset check.

## 4. Settings page

New page **Settings → Patterns** (administrators; sidebar entry next to the other settings
pages), three tabs:

- **Risk signals:** one card per signal (name, description read-only, entries).
- **Classifier:** category and subcategory pickers, then the entries with weights 1–3; a
  subcategory without entries shows "No phrases: Python never names it."
- **Promises:** commitment, conditional, deadline (single regex field) and one card per kind
  with its `supported_by` actions shown read-only.

Entry row: text, Phrase/Regex switch, weight (classifier only), remove. Each list: Add, "Default:
N entries · Reset". Save/Discard footer with the version check, as on the general Settings
page. Risk signals tab: **Recompute signals** button with "Last run: <date>, N of M complaints
changed".

**Test panel** (right column, stacked below on narrow screens), working on the unsaved draft:
*Try a text* (textarea + Test; saved vs draft side by side, matched phrases highlighted) and
*Check against 536 labelled complaints* (button; the comparison from §3 as small before → after
tables with the changed complaints listed). Saving is allowed whatever the results.

## 5. Tests

- Defaults equal the YAML; with defaults, detector, classifier and promise outputs are
  unchanged (existing suites, including the dataset test, stay green).
- Model refusals: a regex that does not compile, nested quantifier, text over 300 characters,
  duplicate entry, unknown or missing signal name, unknown promise kind, weight outside 1–3,
  deadline without its 3 groups, list sizes over the limits.
- Phrase entries match literally (`a.b` does not match `axb`; `caught fire` matches "it caught
  fire").
- Save: unknown subcategory → 422; stale version → 409; other groups unchanged; a saved
  signal entry fires on the next `detect_signals` call without a restart; slow-pattern
  timing → 422.
- Test endpoint: draft vs saved differ for an added phrase; text over 5 000 → 422; dataset
  check returns the four sections and detects a gained signal; time limit → 422.
- Recompute: the task updates a stored complaint's signals and writes the audit entry.
- Access: non-administrators get 403 on all five endpoints.
- Web: type check, lint, build; browser: add the phrase "caught fire" to safety_hazard → Try a
  text shows it firing in the draft only → dataset check runs → Save → Reset → Save.

## 6. Documentation

User guide (Patterns page section), evaluator guide row "Add a risk keyword | Settings →
Patterns → Risk signals → Save → Recompute signals | Database (no code)", project report note
(signals, classifier and promise patterns are settings with a test panel).

## Out of scope

Adding or renaming signals or promise kinds; changing `supported_by`; re-running AI analysis of
stored complaints; analytics, shop and texts (Part 4).
