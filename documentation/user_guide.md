# User Guide (execution instructions)

How to use SupportNova, step by step, in the order the SRS lists (Execution Instructions,
deliverable 13). Screen names are those in the left sidebar.

| Role | What they can do |
|---|---|
| Customer | Submit complaints, track their own complaints |
| Agent | Complaint queue, work on complaints, knowledge base (read), rule matrix (read) |
| Reviewer | Everything an agent can, plus manual review, analytics and reports |
| Manager | Reviewer rights plus users & roles |
| Administrator | Everything, including uploading documents, editing rules, taxonomy and SLAs |

## 1. Log in

Open the site and choose **Sign in** (Clerk). The first sign-in with an e-mail listed in
`BOOTSTRAP_ADMIN_EMAILS` becomes an administrator; everyone else starts as a customer, and an
administrator changes roles under **Users & roles**.

## 2. Upload company documents

**Knowledge base → Upload document** (administrator).

1. Choose a PDF or DOCX file (TXT and Markdown also work).
2. Document ID, category, version and dates are read from the header lines at the top of the
   document (`Document ID: DEL-POL-04`, `Version: 2.0`, ...) or typed in the form.
3. Tick **Activate when processed** to make it the active version as soon as it is ready.
4. The status changes from *Processing* to *Ready*. **Chunks** shows the passages with their
   section, heading and page.

Uploading a new version of an existing document supersedes the old one, and open complaints
whose analysis relied on the old version are flagged for review. A passage that contains
instructions aimed at the AI is shown as *quarantined* and never used.

Bulk import: `uv run python -m knowledge_base.import_documents path/to/folder`.

## 3. Configure complaint rules

- **Rule matrix** (administrator: **New rule**, or the pencil icon to edit). Set the
  category and subcategory (or *Any* for escalation rules), a condition over the listed facts
  (for example `days_late > 5 and shipping_method == 'standard'`), the outcome (department,
  urgency, priority, escalation level), required and prohibited actions, policy references
  and follow-up. Each save is validated, versioned and audited. **Export CSV** downloads the
  matrix.
- **Taxonomy & SLAs**: categories, subcategories, departments and the response and
  resolution targets per priority.

## 4. Submit a complaint

- Customer: **Submit a complaint**. Choose the order it is about (or *No specific order*),
  describe what happened and what you would like us to do.
- Staff: **Complaint queue → Log a complaint** on behalf of a customer (customer reference).

Intake checks run immediately: too-short descriptions, unknown order references and exact
duplicates are rejected with a clear message; card numbers, passwords and ID numbers are
removed; risk signals (safety, injury, privacy, legal, injection...) are detected.

## 5. Analyse the complaint

Analysis starts automatically in the background (the worker must be running). On the
complaint page the status moves from *Analysis queued* to the result, usually within
20 seconds. **Re-run analysis** analyses again, for example after a policy update.

From the command line: `make analyze` (10 dataset complaints) or
`uv run python -m genai_pipeline.analyze --refs CMP-000012`.

## 6. Review the GenAI output

The **AI analysis (Pipeline 1)** section of the complaint page shows the structured JSON result:
summary, primary and secondary issues, sentiment and emotions, urgency with its rationale,
priority, department and supporting departments, cited policy passages, resolution steps,
compensation, escalation notes, the drafted customer response, follow-up, agent guidance,
missing information and clarification questions, and any suspicious instructions found.
The run information shows the prompt version, model, attempts, tokens and latency.

## 7. Run Python validation

Validation runs automatically after each analysis. **Ground-truth validation (Pipeline 2)**
on the complaint page shows the verdict (*Verified*, *Verified with corrections* or
*Needs review*), the score, why a human must review, what Python enforced, the field-by-field
GenAI vs Python table and every check with its evidence. **Re-validate** runs it again (for
example after a rule change).

## 8. Review mismatches

- On a complaint: the **GenAI vs Python** table marks every disagreement with an explanation.
- Across complaints: the dashboard's **GenAI vs Python agreement** panel, and
  **Reports → GenAI / Python Comparison** (preview or export).

## 9. Generate the customer response

The GenAI drafts the response. A reviewer uses **Reviewer decision**:

- **Approve**: send the draft as it is;
- **Modify response**: edit the text, then approve;
- **Regenerate**: run the GenAI again;
- **Reject**: handle manually (a comment is required).

The approved text appears as **Approved customer response**.

## 10. Escalate a complaint

Mandatory escalations are applied automatically by the rules (for example safety →
level 5, data exposure → level 4). To escalate manually: **Reviewer decision → Escalate**
and choose the level (it can never be lowered below what the rules require), or
**Status → Escalated**.

## 11. Review the manual queue

**Manual review** lists complaints that need a human decision, with the reasons: GenAI and
Python disagree, missing policy support, ambiguous complaint, unclear escalation, policy
contradiction, sensitive case (escalation level 4 or 5) or a policy that changed. Open one,
decide (approve, modify, reject, reclassify, reassign, escalate, regenerate, comment); the
decision history keeps the before and after state.

## 12. Track a complaint

- Customers: **My complaints** / the dashboard shows status, department, latest update and
  resolution; the complaint page shows the timeline.
- Staff: **Status → Update status** moves the complaint through the allowed statuses
  (New, Analyzed, Assigned, In progress, Awaiting customer, Escalated, Resolved, Closed,
  Reopened). SLA deadlines and status are shown on the complaint and in the queue.

## 13. View analytics

- **Dashboard**: role-specific. Agents see their department's queue; reviewers, managers and
  administrators see totals, distributions, SLA risks, trends, GenAI/Python agreement and
  review cases.
- **Analytics**: volume over time, category, product, department, urgency, sentiment,
  escalation, channel, customer type, resolution time, department performance, trends and
  policy usage. Filter by date range, category, department, priority, sentiment and channel.

## 14. Generate reports

**Reports**: choose one of the nine reports (Complaint Intelligence, Complaint Analysis,
Department Performance, Escalations, SLA Status, Policy Usage, Resolution Compliance,
GenAI / Python Comparison, Manual Reviews), set filters, preview, then **Export CSV**,
**Export Excel** or **Export PDF**.

From the command line: `make reports` writes the Complaint Intelligence Report to `reports/`.
