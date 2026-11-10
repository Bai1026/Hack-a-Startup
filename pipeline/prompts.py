"""The three model calls. Each one reads lined text ("[CR-p5-L16] ...") and answers with line ids."""

SYSTEM = (
    "You help provider staff analyse insurance denials. You work only from the documents you are "
    "given, never from general knowledge of payer policies. Answer with one JSON object and nothing else."
)

READ = """Below are a denial letter and the payer policy it cites. Every line starts with its id.

<denial_letter>
{letter}
</denial_letter>

<policy>
{policy}
</policy>

Extract the following.

1. The denial reason: the sentences of the letter that state why the request was denied, copied
   character for character.
2. The policy clause the denial rests on. If the letter names one, use it. If it names only a
   section, pick the requirement in that section that the denial reason is about.
3. The stated basis: the policy subsection that contains that clause, with EVERY sibling
   requirement in it, because an appeal has to satisfy all of them.
4. Alternative bases: any other subsection of this same policy that grants coverage for the same
   service by a different route, such as an exception or an "in place of" pathway. Include one only
   if the policy text creates it and you can cite the lines. Limits, definitions, documentation
   rules, exclusions and renewal criteria are not alternative bases. An alternative basis is a
   complete route to coverage on its own: a clause that waives only one requirement of the stated
   basis and leaves the others in force is not one. If there is none, list none.

For each requirement give:
- clause, written like "§3.1(b)". A subsection that is itself the single requirement uses its own
  number, like "§3.2".
- policy_text: the requirement copied character for character from the policy, without the "(a)"
  label, joined across lines with single spaces.
- text: a short paraphrase, under 15 words.
- short_label: a two or three word noun phrase for the requirement, lower case.
- facets: one to three snake_case names, one for each separate thing the record has to show.
  All facets of a requirement must be shown for it to be met, so alternatives ("A or B",
  "unless contraindicated") are never separate facets: use one facet that either route satisfies.
- threshold: if the clause sets a number, {{"comparator": ">=" or "<=", "value": number, "unit":
  "weeks", "label": "what is measured"}}. If it compares two amounts that both come from the
  record (for example one cost against another), use "value": null and name the unit ("USD").
  Otherwise null.

Return:
{{"denial": {{"reason_text": "...", "line_start": "DL-p1-L12", "category": "snake_case_category",
             "policy_id": "...", "policy_title": "...", "clause": "§3.1(c)", "policy_ref_line": "DL-p1-L15"}},
 "bases": [{{"kind": "stated" or "alternative", "clause": "§3.1", "title": "the subsection's own heading, or a short name",
            "line_start": "POL-p1-L11", "line_end": "POL-p1-L11",
            "requirements": [{{"clause": "...", "line_start": "POL-p1-L12", "policy_text": "...", "text": "...",
                              "short_label": "...", "facets": ["..."], "threshold": null}}]}}]}}

For a basis, line_start to line_end cover the lines that introduce the subsection, before its
lettered requirements. policy_ref_line is the line of the letter that names the policy."""

MATCH = """Below is one requirement from a payer policy and a patient's complete clinical record.
Every line of the record starts with its id.

<requirement clause="{clause}">
{policy_text}
</requirement>
Facets the record has to show: {facets}
Threshold: {threshold}

<record>
{record}
</record>

Find the passages of the record that bear on this requirement.

For each passage give:
- line_start: the id of the line where it begins.
- quote: one or two complete sentences copied character for character from the record. Do not
  tidy, shorten or paraphrase. A quote stays on one page.
- relation:
  "supports"     the passage by itself documents that the requirement, or one of its facets, is met.
  "insufficient" on topic but does not establish it.
  "off_target"   mentions the same words but is about something else, such as another time or person.
  "contradicts"  states that the requirement is not met.
- reason: one sentence. For a passage that does not support, say why it falls short.
- key_phrases, for "supports" only: two to four of the shortest substrings of the quote that carry
  a facet (a drug name, a duration, a date range, a dollar figure, an explicit statement), each
  with the facet it carries. Every facet the passage shows needs at least one.
- found_quantity, for "supports" when there is a threshold: {{"value": number, "unit": "...",
  "phrase": "the substring of the quote that states the quantity"}}. If the threshold compares two
  amounts from the record, also give required_quantity in the same form for the other amount.

Rules:
- A plan, an order or an intention is not completion. A patient's own report is not a clinician's
  certification. A statement about the past is not about now. A blank form field is not a "yes".
- When there is a threshold, you do not compare against it; code does. The passage that documents
  the amount actually completed is "supports", with that amount as found_quantity, even when the
  amount is below the threshold. It is never "contradicts" or "insufficient" merely for being
  short. A passage that only states a plan stays "insufficient".
- List at most three supporting passages, the strongest first: a passage that states the
  requirement explicitly comes before one from which it is only implied. Together they must give
  a key phrase for every facet listed above.
- Also list up to three passages that mention this topic but do not satisfy the requirement, the
  closest first. These show staff what was considered and rejected.
- If nothing satisfies the requirement, return no "supports" passage. An empty answer is a correct answer.
- When the requirement is not fully met, add "gap". Otherwise set it to null.

Return:
{{"candidates": [{{"line_start": "CR-p4-L4", "quote": "...", "relation": "supports", "reason": "...",
                  "key_phrases": [{{"text": "...", "facet": "..."}}],
                  "found_quantity": null, "required_quantity": null}}],
 "gap": {{"summary": "one sentence: what is absent or short",
          "what_would_satisfy": "the document or statement that would meet the requirement",
          "suggested_action": "the next step for staff, naming who to ask. Never suggest asserting something the record does not show."}}}}"""

DRAFT = """Write a short appeal letter body for provider staff to review.

Case: {case}
Denial reason: "{denial}"
Policy cited by the denial: {policy}
Basis for this appeal: {basis}

These are the only facts you may use. Each quote has been verified against the record.
{facts}

Return {{"blocks": [{{"type": "text" or "claim", "text": "...", "citations": ["R1-E1"]}}]}}

- Start with one "text" block for the reference line and one "text" block that asks for
  reconsideration and names the basis. End with one "text" block that closes the letter. "text"
  blocks state no clinical facts and have no citations.
- Every clinical or factual statement is a "claim" block of one sentence, citing the ids of the
  evidence it relies on. One claim per requirement is usual.
- A claim says only what its cited quotes say. Every number and date in a claim must appear,
  written the same way, in a quote it cites. Do not put section numbers in a claim.
- Plain, modest wording. Say "the record documents"; never predict the outcome."""
