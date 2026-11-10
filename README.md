# Appealio demo kit

[![Website](https://img.shields.io/badge/Website-Website-blue?style=for-the-badge&logo=github-pages)](https://bai1026.github.io/Hack-a-Startup/)
[![Demo Page](https://img.shields.io/badge/Website-Demo_Page-green?style=for-the-badge&logo=github-pages)](https://bai1026.github.io/Hack-a-Startup/?autoplay=45)



Synthetic cases, an answer key, and a validator for building the Appealio demo.
Start with `PLAN.md`.

**All data here is synthetic.** Every patient, clinician, hospital, payer, policy
number and policy text was written for this kit. Nothing was copied from a real
record or a real payer policy, and every PDF page carries a footer saying so. The
clinical content is plausible but was not reviewed by a clinician; do not present it
as medically validated, and do not use it for anything except this demo.

## Quick check

```
python tools/validate_analysis.py data/cases/A-2048
python tools/validate_analysis.py data/cases/B-3117
python tools/validate_analysis.py data/cases/C-4420
```

Each prints `verification passed`. Python 3.9+, standard library only; installing
`jsonschema` adds the schema check.

## The three cases

| Case | Denial | Record | Expected result |
|---|---|---|---|
| A-2048 | CGRP antagonist for migraine: "insufficient documentation of prior treatment failure" | 5 pages | All 4 requirements supported. Appeal on the stated basis. |
| B-3117 (hero) | Home health after hip surgery: "not medically necessary", homebound status not documented | 8 pages | §3.1(c) missing. Alternative basis §3.3 (home care in place of a facility admission) 3 of 3 supported. Recommend the alternative. |
| C-4420 | Lumbar MRI: conservative therapy requirement not met | 5 pages | §3.1(b) partial, 4 of 6 weeks. Exception §3.2 contradicted by the record. Obtain documentation; no appeal. |

Each record contains distractors: passages that match on keywords and do not
satisfy the requirement. The answer key lists them as `near_misses` with the reason.

| Case | Distractor | Why it fails |
|---|---|---|
| A-2048 | Amitriptyline taken for about 2 weeks (p1 L13-14) | Under the 8-week minimum |
| A-2048 | Propranolol "considered but not started" (p2 L14) | No trial took place |
| A-2048 | "Plan to continue so that she completes an adequate trial" (p3 L9) | An intention at week 4 |
| B-3117 | "Member is homebound: [ ] Yes [ ] No ... (left blank)" (p5 L16) | Blank form field |
| B-3117 | "Before this admission the patient was not homebound" (p4 L4-5) | About the past, and negative |
| B-3117 | "mostly been staying in since coming home" (p8 L5-6) | Patient report relayed by a nurse |
| C-4420 | "Physical therapy 2 visits per week for 6 weeks" (p3 L13) | The plan; not completed |
| C-4420 | "Home exercise program handout issued" (p3 L15) | Unsupervised, no log |
| C-4420 | "home exercises most days since leaving physical therapy" (p5 L6-7) | Self-reported, one week |

## Files in a case folder

### PDFs
`denial_letter.pdf`, `policy.pdf`, `clinical_record.pdf`. US Letter, 612 by 792
points. Every body line has its number printed in the left margin. Numbering
restarts on each page. The page header and footer are not numbered and are not in
the line index.

### `lines/<doc>.lines.json`
The line index for one PDF. It is the source of truth for citations.

```json
{
  "doc_id": "CR",
  "file": "clinical_record.pdf",
  "page_size": [612.0, 792.0],
  "coord_origin": "top-left",
  "units": "pt",
  "pages": [
    {"page": 5, "lines": [
      {"line_id": "CR-p5-L16", "line": 16, "style": "body",
       "text": "Member is homebound: [ ] Yes [ ] No. Clinical findings supporting homebound status: (left blank).",
       "bbox": [76.0, 356.68, 503.41, 368.48]}
    ]}
  ]
}
```

- `doc_id`: `DL` denial letter, `POL` policy, `CR` clinical record.
- `line_id`: `<doc_id>-p<page>-L<line>`.
- `bbox`: `[x0, y0, x1, y1]` in points, origin at the **top-left** of the page.
- `style`: `heading` or `body`.

### `text/<doc>.lined.txt`
The same lines as plain text, one per row, for prompts:

```
=== CR | Clinical record | page 5 of 8 ===
[CR-p5-L15] Homebound status
[CR-p5-L16] Member is homebound: [ ] Yes [ ] No. Clinical findings supporting homebound status: (left blank).
```

### `analysis.gold.json`
The answer key, in the format the pipeline must produce and the front end reads.
Schema: `data/schema/analysis.schema.json`. Shape:

```
denial            reason_text (verbatim), source span, policy_ref
bases[]           the stated basis first, then alternative bases
  requirements[]  clause, text, policy_text, facets, status
    evidence[]    evidence_id, source span, quote, key_phrases[], rationale
    near_misses[] source span, quote, relation, why_not
    quantity_check  label, comparator, required, found, passed
    gap             summary, what_would_satisfy, suggested_action
  counts, supportable
recommendation    type, basis_id, banner, rationale, human_actions[]
draft             basis_id, status, blocks[] (text | claim | gap) with citations[]
```

A span is `{doc_id, page, line_start, line_end, rects}`. A passage never crosses a
page. `rects` has one rectangle per line the passage touches, tight around the
quoted characters. Key phrases carry their own `rects`.

Quote rule: join the `text` of lines `line_start` to `line_end` with single spaces
and collapse whitespace. The quote is a substring of that string.

Statuses: `supported`, `partial`, `missing`, `contradicted`.
Near-miss relations: `insufficient`, `off_target`, `contradicts`.

### `case.json`
Patient, payer, provider, service requested, request and denial dates, appeal
deadline (180 days after the denial), and the document list.

## Validator

```
python tools/validate_analysis.py <case_dir> [analysis.json] [--json]
```

With no second argument it checks the answer key. With one, it verifies that file
and scores it against the answer key.

Verification, exit code 1 on failure: schema, cited lines exist, quotes are
verbatim, key phrases are substrings of their quote, rectangles sit on cited lines,
statuses and counts are consistent, the recommendation follows the decision rule,
every draft claim cites verified evidence for a supported requirement, and every
number in a claim appears in a quote it cites.

Scoring, printed only: status accuracy, evidence recall and precision (a predicted
passage counts when it shares a page and at least one line with an answer-key
passage for the same clause), distractor hits (a predicted passage that lands on a
near miss), and whether the recommendation matches. Requirements are matched to the
answer key by their `clause` string, so the pipeline must output clauses in the
form `§3.1(b)`.

## Regenerating or adding cases

```
pip install reportlab
python tools/generate/build_kit.py
```

`tools/generate/case_*.py` hold the document text and the answer key. Passages are
marked inline as `[[span_id]]text[[/span_id]]` and the answer key refers to span
ids, so page numbers, line numbers and rectangles are computed, never typed. To add
a case, copy one of the files, edit it, and add the module to `main()` in
`build_kit.py`. The build fails if a key phrase is not inside its passage, if a
quantity check contradicts its numbers, or if a recommended basis is not fully
supported.
