# Evaluation: unseen complaints, GenAI vs Python, latency

SRS deliverable 8 requires comparing at least 100 unseen complaints. This document explains
how the evaluation is run, what the Python-only results are, and how the GenAI results and
latency are produced.

## 1. Data

| Set | Complaints | Purpose |
|---|---|---|
| `sample_complaints/` | 536 (531 accepted, 5 intentional exact duplicates rejected) | Development: the classifier lexicons and rule matrix were built against it |
| `hidden_test_ready/holdout/` | 109 (108 accepted; 1 deliberately too short, rejected at intake) | **Unseen** evaluation set |

The hold-out complaints (`build_holdout.py`) were written separately from the dataset
generator, in different wording and styles: slang and lower case, capitals and exclamation
marks, non-native English, very short and long messages, calm reports of dangerous
situations, angry reports of minor issues, multi-issue complaints, customers quoting invented
policies, fake staff notes and injected instructions. All 12 categories are covered.

Each complaint is labelled with the category and subcategory a support lead would assign,
other acceptable categories for genuinely ambiguous cases, the sentiment, whether escalation
is expected, whether clarification is needed and whether it contains a prompt injection.
Routing, urgency and priority follow from the category through the rule matrix, so they are
scored through the category and escalation labels rather than labelled separately.

## 2. How to run

```bash
make evaluate-python   # Pipeline 2 alone (no API key needed, writes nothing to the database)
make evaluate          # Pipeline 1 + Pipeline 2 for every complaint, with timing (API key)
```

Evaluator packs use the same format (`complaints.jsonl`, optional `customers.csv` and
`orders.csv`; labels optional):

```bash
uv run python -m comparison_engine.evaluate path/to/pack
```

Outputs: `reports/evaluation_<pack>.csv` with the SRS columns (complaint ID, expected
category, GenAI and Python category, department, urgency and escalation, policy references,
match/mismatch, verification status, explanation of each disagreement) plus latency, and
`reports/evaluation_<pack>_summary.json`.

## 3. Python-only results (Pipeline 2 without GenAI)

### 3.1 First run on the unseen set

| Measure | Development dataset | Hold-out (unseen) |
|---|---|---|
| Category accuracy (acceptable categories) | 94.9% | **58.3%** |
| Escalation agreement with labels | 100% | **86.1%** |

Broken down by the classifier's own confidence, the first hold-out run showed:

| Classifier confidence | Complaints | Category accuracy |
|---|---|---|
| Confident | 53 | 98.1% |
| Tentative | 16 | 68.8% |
| Unknown (abstains) | 39 | n/a (no category is guessed) |

The drop in overall accuracy is almost entirely abstention: on wording it has not seen, the
keyword classifier says "unknown" instead of guessing, and Pipeline 2 then skips the category
check and relies on the GenAI plus a reviewer. When it does commit to a category it is almost
always right.

The escalation result was more important: Python **missed 9 expected escalations**, all in
sensitive categories. Examples: "the adapter sparked and smelled burnt" (the lexicon had
"sparks" and "burnt smell" but not those verb forms), "it wasn't me" (account takeover),
"a login from a device I don't own", "did you share my details?", a toddler getting hold of
a battery and a trip to A&E.

### 3.2 Fix and second run

The risk-signal lexicons in `config/detectors.yaml` were extended with general patterns (verb
forms of spark/smell/burn, battery-cover and swallowing hazards, A&E, ambulance, cuts and
bleeding, unrecognised logins and devices, "wasn't me", "I never ordered", data sent to the
wrong person, "did you share my details"). The development dataset was re-checked afterwards
and did not change (escalation still 100%, category 94.9%).

| Measure | Hold-out, first run | Hold-out, after lexicon fixes |
|---|---|---|
| Category accuracy | 58.3% | 66.7% |
| Confident classifications correct | 98.1% (52/53) | 100% (61/61) |
| Escalation agreement | 86.1% | 94.4% |
| Missed escalations | 9 | **0** |
| Extra escalations (safe direction) | 6 | 6 |

The second run is no longer strictly unseen for the lexicons, because the misses informed
the fixes. We report both runs for that reason. A fresh evaluator pack gives the clean number.

### 3.3 What the remaining disagreements are

All remaining escalation disagreements are Python escalating when the label did not: for
example the second missed return pickup (repeat-contact rule), a policy claim in the text,
or a third repair. These follow documented rules and err on the side of human review.

## 4. GenAI vs Python and latency

`make evaluate` runs the full pipeline (retrieval, prompt, Claude structured output,
validation, Python checks) for each hold-out complaint and records the wall-clock time of each
one against the SRS target of 20 seconds. The summary reports:

- GenAI and Python category accuracy against the labels;
- GenAI/Python agreement per field (category, department, urgency, priority, escalation);
- verification outcomes (verified, verified with corrections, needs review);
- latency: median, 95th percentile, maximum and share within 20 seconds.

**Status:** to be run once `ANTHROPIC_API_KEY` is configured. Paste the summary
(`reports/evaluation_holdout_summary.json`) here:

| Measure | Result |
|---|---|
| GenAI category accuracy | _pending_ |
| GenAI escalation agreement | _pending_ |
| GenAI/Python agreement (category / department / urgency / priority / escalation) | _pending_ |
| Verified / corrected / needs review | _pending_ |
| Latency median / p95 / max | _pending_ |
| Within 20 s | _pending_ |

## 5. Threats to validity

- The hold-out labels were written by the same team that built the system.
- Routing, urgency and priority are scored through the category, not labelled separately.
- The second Python run is informed by the first (see 3.2).
- Latency depends on the model, effort setting and provider load at the time of the run.
