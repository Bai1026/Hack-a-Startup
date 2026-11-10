# Appealio demo: build plan for the coding agent

You are building a short product demo for Appealio, an entry in CMU's Hack-a-Startup.
Appealio helps provider staff turn an insurance denial into an appeal in which every
claim links back to the clinical record, and in which missing evidence is shown as
missing.

Read this file first, then `README.md` for the data formats.

## 1. What done looks like

A web app that plays a 30 to 60 second click-through on one synthetic case and shows
three things, in this order:

1. **Linked evidence.** The denial is broken into policy requirements. Clicking a
   requirement jumps the source viewer to the exact lines in the record, with the key
   phrases highlighted.
2. **A visible gap.** One requirement has no supporting passage. The app says
   "Evidence missing", shows the closest passages it found, and says why each one
   falls short.
3. **An alternative basis.** The same policy offers a second route to coverage. The
   record supports every requirement on that route, so the app recommends appealing
   on it, and the draft letter switches to it.

The banner on the hero case reads:

> Evidence missing for homebound certification (§3.1(c)). Recommend appealing under
> §3.3, home-based care in place of a facility admission: 3 of 3 requirements supported.

Everything is driven by one JSON file per case (`analysis.json`). The kit ships an
answer key in that exact format for each case, so the front end can be finished
before the pipeline exists.

### Out of scope

Login, database, file upload, EHR or payer integration, real patient data, automatic
submission, mobile layout. Add none of these.

## 2. What is in this kit

```
PLAN.md                         this file
README.md                       data formats and how the cases were made
data/
  cases/index.json              the three cases and their expected outcome
  cases/<case_id>/
    denial_letter.pdf           1 page
    policy.pdf                  1 page
    clinical_record.pdf         5 to 8 pages
    lines/*.lines.json          every numbered line of each PDF: id, text, bbox
    text/*.lined.txt            the same lines as "[CR-p5-L16] text", ready for a prompt
    case.json                   metadata (patient, payer, dates)
    analysis.gold.json          answer key, in the pipeline's output schema
  schema/analysis.schema.json   JSON Schema for analysis.json
  demo/demo_script.json         timed click-through for the recording
tools/
  validate_analysis.py          verifies an analysis and scores it against the answer key
  generate/                     regenerates the cases (reportlab)
```

| Case | Scenario | Expected outcome |
|---|---|---|
| **B-3117** (hero) | Home health denied: homebound status not documented | Stated basis 2 of 3, one **missing**. Alternative basis §3.3: 3 of 3. Recommend the alternative. |
| A-2048 | CGRP antagonist denied: prior treatment failure not documented | 4 of 4 supported. Appeal on the stated basis. Same example as slide 4 of the deck. |
| C-4420 | Lumbar MRI denied: conservative therapy incomplete | One requirement **partial** (4 of 6 weeks). The policy's exception is **contradicted** by the record. Recommend obtaining documentation; no appeal. |

Every PDF prints its line numbers in the left margin, so "p5, lines 10-11" can be
checked by eye.

## 3. The demo

Default cut is 45 seconds on case B-3117. `data/demo/demo_script.json` has the exact
steps, targets, timings and the presenter's lines for the 30, 45 and 60 second cuts.

| Time | On screen | Presenter |
|---|---|---|
| 0:00 | Case B-3117 opens. Denial reason highlighted in the letter. | "Home health was denied. The insurer says the record does not show the patient is homebound." |
| 0:06 | Click **Analyze**. Requirement rows resolve: two green, one red, then three green under the alternative basis. Banner slides in. | |
| 0:10 | Click the evidence chip on §3.1(b). Record jumps to p5 L10-11, key phrases highlighted. | "Appealio breaks the policy into requirements and links each one to the exact lines in the record." |
| 0:18 | Click §3.1(c). Missing-evidence card opens. Click the first closest passage: p5 L16, the blank form field. | "For homebound status, nothing qualifies. The form section was left blank. So it says evidence missing. It does not write around the gap." |
| 0:28 | Click **Use this basis** in the banner. Click the evidence chip on §3.3(c): p6 L14-15, both cost figures highlighted. | "The same policy covers home care in place of a facility stay, and the record supports all three conditions. Including cost: 4,350 dollars at home against 10,400 in a facility." |
| 0:39 | Draft panel, citation chips visible. | "The draft says only what the record shows. Every sentence links back. Staff review and submit." |

The 30 second cut drops the 0:10 beat. The 60 second cut adds 15 seconds on C-4420,
where the app declines to recommend an appeal.

Build an autoplay mode (`?autoplay=45`) that replays the script, so every take is
identical. Record at 1920x1080. Nothing in the recording calls a model: the app loads
a saved `analysis.json`.

**Rule for the recording:** load the pipeline's output, after it passes the validator.
The answer key is for building the UI. The footer shows which file is loaded
(`generated_by`); do not hide it.

## 4. Screen design

One screen. The layout keeps the three columns from slide 4 of the deck and adds a
banner and two-way linking.

```
+-----------------------------------------------------------------------------------------+
| Appealio   Case B-3117  Home health after hip fracture surgery    [A-2048][B-3117][C-4420]
| DENIED  "...do not document that the member is homebound."   Letter p1 L12-13   §3.1(c) |
+-----------------------------------------------------------------------------------------+
| (!) Evidence missing for homebound certification (§3.1(c)). Recommend appealing under   |
|     §3.3, home-based care in place of a facility admission: 3 of 3 requirements         |
|     supported.                                                       [ Use this basis ] |
+---------------------------+-------------------------------------+-----------------------+
| REQUIREMENTS              | SOURCE   [Record] [Policy] [Letter] | APPEAL DRAFT          |
|                           | page 5 of 8                         | basis: §3.3           |
| Stated basis §3.1    2/3  |                                     |                       |
|  v (a) Order after F2F    |  9  Skilled nursing need            | We request ...        |
|     p5 L4-5   p5 L7-8     | 10 |Skilled nursing is needed| for.. |                       |
|  v (b) Skilled need       | 11  and pain medication management. | The member meets Plan |
|     p5 L10-11  p4 L13-14  |                                     | criteria for ... [1]  |
|  x (c) Homebound cert.    | 15  Homebound status                |                       |
|     EVIDENCE MISSING      | 16 :Member is homebound: [ ] Yes..: | Her home was ... [2]  |
|     3 closest passages    |                                     | [3]                   |
|                           |                                     |                       |
| Alternative basis §3.3 3/3|                                     | The expected cost ... |
|  v (a) Meets SNF criteria |                                     | [4]                   |
|  v (b) Home safe, carer   |                                     |                       |
|  v (c) Cost not higher    |                                     | Review required       |
+---------------------------+-------------------------------------+-----------------------+
| Searched 138 lines in 8 pages   8 passages cited   3 near misses   source: pipeline     |
+-----------------------------------------------------------------------------------------+
```

### Header
Case title, case switcher, the denial reason quoted verbatim. The quote is a link:
it opens the Letter tab at `denial.source`. The clause chip opens the Policy tab at
`denial.policy_ref.source`.

### Banner
`recommendation.banner`, one sentence. Three variants by `recommendation.type`:

- `appeal_on_stated_basis`: green, no button.
- `appeal_on_alternative_basis`: amber, with **Use this basis**. The button expands
  the alternative group, scrolls to it, and shows the draft.
- `obtain_documentation`: red, lists `recommendation.human_actions`.

### Requirements column (the navigation)
One group per entry in `bases`, with a `supported/total` counter. One row per
requirement: status icon, clause, `text`, and one chip per evidence item labelled
`p5 L10-11`. Clicking a chip selects that evidence. Clicking the clause opens the
Policy tab at `policy_source`.

A selected row expands to show:

- the quote, with key phrases bold;
- one facet chip per facet, for example `duration: eight-week trial`. A facet with no
  key phrase shows as an empty chip;
- the quantity check, if any: `Trial duration: found 8 weeks, required at least 8`;
- the rationale.

Status styles:

| Status | Icon and color | Row content |
|---|---|---|
| `supported` | check, green | evidence chips |
| `partial` | half circle, amber | evidence chips, failed quantity check, gap card |
| `missing` | cross, red | "Evidence missing" gap card |
| `contradicted` | cross, red | "Record indicates otherwise" gap card |

### Gap card
Shown for every status except `supported`. This is the second beat of the demo, so
give it room.

```
EVIDENCE MISSING                                                    §3.1(c)
No practitioner certification of homebound status anywhere in the record.
Would satisfy: a signed statement by the treating practitioner that the member
is homebound, with the clinical findings that support it.

Closest passages (none sufficient)
  p5 L16    "Member is homebound: [ ] Yes [ ] No. Clinical findings ..."
            The homebound section of the form was left blank.
  p4 L4-5   "Before this admission the patient was not homebound; ..."
            Describes her status before the fracture.
  p8 L5-6   "The patient says she has mostly been staying in ..."
            A nurse's record of what the patient said, not a certification.

Next step: if it is clinically accurate, ask Dr. Abernathy to complete the
homebound section. Do not assert homebound status without it.
```

Fields: `gap.summary`, `gap.what_would_satisfy`, `near_misses[]` (`quote`,
`why_not`), `gap.suggested_action`. Each closest passage is a link into the record.
Showing them is what makes "missing" credible: the viewer sees the app looked, found
the word "homebound" three times, and rejected all three for a stated reason.

### Source column
Tabs for Record, Policy and Letter. Render each PDF page with pdf.js onto a canvas
and draw highlights as absolutely positioned divs on top.

All rectangles in `analysis.json` are `[x0, y0, x1, y1]` in PDF points with the
origin at the top-left of the page, and pages are 612 by 792. At render scale `s`:
`left = x0*s, top = y0*s, width = (x1-x0)*s, height = (y1-y0)*s`. No axis flip.

Two highlight layers for the selected evidence:

- a pale band over `source.rects` (the whole passage);
- a stronger fill over each `key_phrases[].rects`.

Near misses get a dashed gray outline; contradicting passages a dashed red one;
policy clauses and the denial reason a blue band. Only the selected item is drawn at
full strength. On selection, switch to the right tab, scroll so the first rect sits
about a third of the way down, and pulse the highlight once.

### Draft column
Render `draft.blocks` as a letter. `claim` blocks end with one numbered chip per
citation; clicking a chip selects that evidence, the same as clicking it in the
requirements column. `gap` blocks render as a dashed amber placeholder. When
`draft.status` is `blocked_on_gaps`, show "Not ready to send" above the letter and
disable Export. Always show "Review required: verify each passage before submission."

### Linking model
One piece of state: the selected item (an evidence id, a near-miss, a policy span or
the denial span). All three columns read it. Selecting anywhere updates everywhere.

## 5. How evidence matching works

The pipeline turns three documents into one `analysis.json`. Three model calls do
the reading; code does the checking and the deciding. The model proposes, and
nothing reaches the screen unless code confirms it against the source text.

```
denial letter + policy --[1 READ]--> requirements, grouped into bases
requirement + record   --[2 MATCH]-> candidate passages with key phrases
candidates             --[3 VERIFY]-> verified evidence, statuses      (code)
statuses               --[4 DECIDE]-> recommendation                   (code)
verified evidence      --[5 DRAFT]--> letter with citations, re-checked by code
```

Input to every model call is the `.lined.txt` text, where each line starts with its
id (`[CR-p5-L16] ...`). The model answers with line ids, so every answer is
checkable.

### Stage 1: Read (one model call)
Input: denial letter and policy, lined. Output:

- the denial reason, verbatim, with its line ids;
- the policy clause the denial cites;
- the **stated basis**: the policy subsection that contains the cited clause, with
  every sibling requirement in it. The denial for B-3117 cites only §3.1(c), but an
  appeal has to satisfy (a), (b) and (c), so all three are extracted;
- **alternative bases**: any other subsection of the same policy that grants coverage
  for the same service by a different route, such as an exception or an
  "in place of" pathway;
- for each requirement: clause, verbatim policy lines, a short paraphrase, two or
  three **facets**, and a threshold if the clause has one.

A facet is one thing the record has to show. "A trial of at least 8 weeks of a
preferred medication" has two: `medication` and `duration`. Facets are what key
phrases get attached to in the next stage.

A threshold is `{comparator, value, unit}`: `>= 8 weeks`, `>= 4 migraine days per
month`, `<= facility cost`.

**Alternative bases come only from the supplied policy text.** The model must cite
the lines that create the pathway. If the policy has no such clause, there is no
alternative basis. Never let the model propose an appeal argument from general
knowledge.

### Stage 2: Match (one model call per requirement, in parallel)
Input: one requirement and the whole lined record. These records are 5 to 8 pages,
so send all of it; no retrieval step is needed at this size.

Output, per requirement, a list of candidate passages:

```json
{
  "line_start": "CR-p4-L4", "line_end": "CR-p4-L4",
  "quote": "Patient completed an eight-week trial of topiramate, 06/08/2026 to 08/03/2026.",
  "relation": "supports",
  "key_phrases": [
    {"text": "eight-week trial", "facet": "duration"},
    {"text": "topiramate", "facet": "medication"}
  ],
  "found_quantity": {"value": 8, "unit": "weeks", "phrase": "eight-week trial"},
  "reason": "States a completed trial of a preferred medication and its length."
}
```

`relation` is one of `supports`, `insufficient`, `off_target`, `contradicts`. Ask
for the non-supporting ones explicitly: "also list passages that mention this topic
but do not satisfy the requirement, and say why". Those become the near misses.

Prompt rules that matter:

- Quote exactly. Copy characters from the cited lines; do not tidy or paraphrase.
- Key phrases are the shortest substrings of the quote that carry a facet: a drug
  name, a duration, a date range, a dollar figure, an explicit statement. Two to four
  per passage.
- A plan, an order or an intention is not completion. A patient's report is not a
  clinician's certification. A statement about the past is not about now. A blank
  form field is not a "yes".
- If nothing satisfies the requirement, return no `supports` candidates. An empty
  answer is a correct answer.

Why this is a model call and not keyword search. The cases are built so that keyword
matching fails in both directions:

- B-3117: "homebound" appears three times in the record. None certifies homebound
  status; one says she was *not* homebound.
- C-4420: "6 weeks" appears in the therapy plan. The discharge note shows the plan
  was not completed.
- A-2048: the passage that proves the 8-week trial says "eight-week", in words, and
  a different medication was taken for "2 weeks".

### Stage 3: Verify (code only)
For every candidate:

1. Resolve the line ids. Unknown id: drop the candidate.
2. Join the cited lines with single spaces, collapse whitespace, and check that the
   quote is a substring. If it is not, search the whole record for the quote and
   re-anchor to the lines where it occurs. Still not found: drop the candidate.
3. Drop any key phrase that is not a substring of the quote.
4. Run the quantity check in code. Parse the number from `found_quantity.phrase`
   (handle "six", "eight-week", "4 weeks", "$4,350") and compare it with the
   threshold. Do not trust the model's own comparison.
5. Compute rectangles, one per line touched. For the passage, use each cited
   line's `bbox` from `lines.json`. For a key phrase, use PyMuPDF
   `page.search_for(phrase, clip=line_bbox)` on the PDF. `search_for` can return
   nothing for a phrase that wraps onto a second line, so split the phrase at the
   line break (the line texts in `lines.json` tell you where) and search each part
   inside its own line. The validator accepts rects within 4 points of a cited line.

Then set the requirement's status:

| Status | Rule |
|---|---|
| `supported` | at least one verified `supports` passage, every facet has a key phrase, and the quantity check passes or there is none |
| `partial` | verified `supports` passage exists, but a facet is uncovered or the quantity check fails |
| `contradicted` | no `supports` passage and at least one verified `contradicts` passage |
| `missing` | none of the above |

Every status except `supported` gets a `gap` (summary, what would satisfy it,
suggested action). The model may write the gap text; the status itself comes from
this table.

### Stage 4: Decide (code only)
```
if every requirement of the stated basis is supported:
    appeal_on_stated_basis
elif some alternative basis has every requirement supported:
    appeal_on_alternative_basis      (first such basis in policy order)
else:
    obtain_documentation
```

Build the banner from a template so its wording is stable:

- stated: `All {n} requirements under {clause} are supported by the record. Ready for staff review.`
- alternative: `Evidence {missing|incomplete} for {label} ({clause}). Recommend appealing under {alt_clause}, {alt_title}: {k} of {k} requirements supported.`
- none: `Evidence {missing|incomplete} for {clause}: {gap.summary} No alternative basis is supported by this record. {next step}`

### Stage 5: Draft (one model call, then code)
Input: the recommended basis and its verified evidence only (ids and quotes). The
model never sees unverified text at this stage. Output: `blocks`, where each `claim`
lists the evidence ids it relies on.

Code then rejects the draft and retries if:

- a claim cites an id that does not exist, or evidence belonging to a requirement
  that is not `supported`;
- a claim has no citation;
- a number or date in a claim does not appear in any quote it cites.

If no basis is supportable, do not ask for a letter. Emit the supported claims plus
one `gap` block per unsupported requirement, with `status: blocked_on_gaps`.

### The same checks, as a tool
`tools/validate_analysis.py` implements stages 3 and 4 as assertions, plus the draft
checks, and scores against the answer key:

```
python tools/validate_analysis.py data/cases/B-3117 out/B-3117.json
```

Run it as the last step of the pipeline. A run that fails verification writes no
output.

## 6. Architecture

```
pipeline/            Python 3.11+
  read.py  match.py  verify.py  decide.py  draft.py  run.py
  prompts/           one file per model call
web/                 Vite + React + TypeScript + Tailwind + pdfjs-dist
  public/cases/      copy of data/cases, plus analysis.json per case
out/                 pipeline output, one JSON per case
```

- **No server at demo time.** The web app is static and fetches
  `cases/<id>/analysis.json` and the three PDFs.
- **Pipeline CLI:** `python -m pipeline.run data/cases/B-3117 --out out/B-3117.json`.
  It validates before writing. `make demo` runs all three cases and copies verified
  output into `web/public/cases/<id>/analysis.json`.
- **Model access:** any model that can return JSON matching a schema. Put the model
  id and API key in environment variables. Temperature 0. Cache each call's response
  on disk keyed by a hash of the prompt, so reruns are free and stable.
- **Line index:** use the provided `lines.json` files. Do not re-parse the PDFs for
  the three demo cases. Parsing arbitrary PDFs is a stretch goal.
- **Dev toggle:** `?source=gold` loads `analysis.gold.json` instead. The footer
  always shows `generated_by`.

## 7. Milestones and acceptance checks

**M0. Scaffold.** Repo layout above; `data/` copied into `web/public/cases`.
- `python tools/validate_analysis.py data/cases/<id>` passes for all three cases.

**M1. Front end on the answer key.** The whole of section 4, loading
`analysis.gold.json`.
- B-3117: clicking each of the 8 evidence chips switches to the Record tab, scrolls
  to the right page, and the highlight covers the text named in the chip. Check
  three by eye against the printed line numbers.
- Key-phrase highlights sit on the phrase, within 2 pixels at 100% zoom.
- §3.1(c) shows the gap card with three closest passages, each clickable.
- **Use this basis** expands §3.3 and shows the draft; each citation chip in the
  draft selects the same evidence as its chip in the requirements column.
- A-2048 shows a green banner and no gap card. C-4420 shows a red banner, a partial
  row with "found 4 weeks, required at least 6", a contradicted row, and a disabled
  Export.

**M2. Autoplay.** `?autoplay=30|45|60` replays `data/demo/demo_script.json`.
- Two consecutive runs are visually identical. Total time is within 1 second of the cut.

**M3. Pipeline.** Stages 1 to 5.
- All three outputs pass verification.
- Against the answer key, on every case: status accuracy 1.0, recommendation
  correct, distractor hits 0, evidence recall at least 0.8.
- Stage 1 extracts §3.3 as an alternative basis for B-3117 and §3.2 for C-4420, and
  no alternative basis for A-2048.
- Deleting a cited sentence from a copy of the record and rerunning turns that
  requirement `missing`. It must not be backfilled from elsewhere.

**M4. Record.** Switch the app to pipeline output, run autoplay, capture at 1920x1080.

**Stretch, only after M4.**
- A baseline for the pitch: one prompt asking a model to "write the appeal with
  citations" from the same three documents, run through the validator. Report how
  many of its citations fail verification next to the pipeline's zero.
- Upload of arbitrary PDFs: PyMuPDF `get_text("words")`, group words into lines by
  baseline, write the same `lines.json` format.

M1 and M2 need no model access and are enough to rehearse the demo. Build them first.

## 8. Guardrails

- **Synthetic data only.** Every person, organization, policy and record in this kit
  is fictional, and every page says so. Do not add real patient data, real payer
  names or real policy text.
- **No invented evidence.** If verification removes the only support for a
  requirement, the requirement becomes `missing`. Never weaken the check to make a
  case pass.
- **No invented arguments.** An alternative basis exists only when the supplied
  policy has a clause for it and the pipeline can cite that clause.
- **The app recommends; staff decide.** Keep "Review required" on screen. There is
  no submit action.
- **Keep the wording modest.** Use "supported by the record", not "approved" or
  "will be overturned". The app does not predict outcomes.
- **Secrets** stay in environment variables and out of the repo and the recording.
