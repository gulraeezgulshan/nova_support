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

`make evaluate` runs the full pipeline (retrieval, prompt, structured output, validation,
Python checks) for each hold-out complaint and records the wall-clock time of each one
against the SRS target of 20 seconds.

Run: 28 September 2026, OpenAI `gpt-5-mini`, `GENAI_EFFORT=low`, all 108 accepted hold-out
complaints, 0 provider failures in the final run. Outputs:
`reports/evaluation_holdout.csv` and `reports/evaluation_holdout_summary.json`.

### 4.1 Accuracy and agreement

| Measure | Result |
|---|---|
| GenAI category accuracy (acceptable categories) | **95.4%** |
| Final category accuracy after Python validation | **98.1%** |
| GenAI escalation agreement with labels | 81.5% |
| Final escalation agreement after Python validation | **94.4%** (0 missed escalations) |
| GenAI/Python agreement: category / department / urgency / priority / escalation | 95.4% / 84.3% / 51.9% / 52.8% / 75.0% |
| Verified / verified with corrections / needs review | 25 / 29 / 54 |

"Final" is the category and escalation that the complaint ends up with: Python's own answer
when its classifier is confident, otherwise the GenAI category accepted provisionally (see
`python_validation/checks.py`). Together the two pipelines are more accurate than either
alone: the GenAI category is right on most complaints the keyword classifier cannot place,
and Python's rules catch the escalations the model under-rates.

The low urgency and priority agreement is expected. The model grades urgency from the tone
and wording; Python derives it from the rule matrix (category, risk signals, repeat contact,
customer tier). They mostly differ by one step, and Python's value is the one applied. The
disagreement is why half the complaints go to review: a reviewer sees both values and the
reason for each.

### 4.2 Latency

| Segment | Timed | Median | p95 | Max | Within 20 s |
|---|---|---|---|---|---|
| First run (interrupted by a network error) | 54 | 28.5 s | 81.6 s | 118.6 s | 3.7% |
| Final run (resumed, completed all 108) | 48 | 33.3 s | 71.2 s | 127.7 s | 2.1% |

**The 20-second target is not met** with this model and setting. The run was interrupted
twice by network errors from the provider; `comparison_engine/evaluate.py` now retries a
complaint up to three times (waiting 30 s, then 60 s), and complaints already analysed are
not re-timed when a run resumes, so the two segments together time 102 of the 108 (the
rest were analysed in the short second run, whose timings were not kept).

Almost all of the time is the model call (reasoning plus structured output); retrieval and
the Python checks take well under a second. Ways to meet the target, not yet measured:
`GENAI_EFFORT=minimal`, a faster model (`OPENAI_MODEL` / `ANTHROPIC_MODEL` is one setting),
or a shorter prompt with fewer policy passages. Analysis runs on the worker, so the customer
gets their complaint reference immediately and the analysis appears when it is ready.

### 4.3 Comparison report on all analysed complaints

`reports/genai_python_comparison.csv` (Reports → GenAI vs Python) covers every complaint in
the database that has an analysis: 118 (the 108 hold-out complaints plus 10 from the
development dataset); 26 verified, 32 corrected, 60 need review. Agreement: category 94.9%,
department 83.9%, urgency 53.4%, priority 55.1%, escalation 76.3%.

Accuracy in that report is only scored on fields that have a label. The hold-out labels have
the category (118 labelled) but not department, urgency or priority, so those fields are
scored only on the 10 development complaints that carry them. Treat the department, urgency,
priority and escalation accuracies there (GenAI 100% / 70% / 80% / 90%, Python 80% / 100% /
100% / 100%) as a small sample; the category figures (GenAI 90.7%, Python 94.1%) are the
meaningful ones.

## 5. Threats to validity

- The hold-out labels were written by the same team that built the system.
- Routing, urgency and priority are scored through the category, not labelled separately.
- The second Python run is informed by the first (see 3.2).
- Latency depends on the model, effort setting and provider load at the time of the run.
- Department, urgency and priority accuracy in the comparison report rests on 10 labelled complaints.
