"""Appealio pipeline: denial letter + policy + clinical record -> analysis.json.

    python -m pipeline.run data/cases/B-3117            # writes data/cases/B-3117/analysis.json
    python -m pipeline.run --all

The model proposes (stages 1, 2, 5). Code checks and decides (stages 3, 4, and the
draft checks). Nothing is written unless tools/validate_analysis.py passes.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import pymupdf

from . import prompts

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "out" / "cache"
MODEL = os.environ.get("APPEALIO_MODEL", "claude-sonnet-5-5")
DOC_FILES = {"DL": "denial_letter", "POL": "policy", "CR": "clinical_record"}


# ---------------------------------------------------------------- model access

def load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


def ask(prompt):
    """One model call that returns JSON. Cached on disk by a hash of the prompt."""
    key = hashlib.sha256(f"{MODEL}\n{prompt}".encode()).hexdigest()[:24]
    hit = CACHE / f"{key}.json"
    if hit.exists():
        return json.loads(hit.read_text())
    import anthropic
    client = anthropic.Anthropic()
    kwargs = dict(model=MODEL, max_tokens=8000, system=prompts.SYSTEM,
                  messages=[{"role": "user", "content": prompt}])
    # This SDK version takes no temperature; the disk cache is what keeps reruns stable.
    msg = client.messages.create(**kwargs)
    text = "".join(b.text for b in msg.content if b.type == "text")
    data = json.loads(text[text.index("{"): text.rindex("}") + 1])
    CACHE.mkdir(parents=True, exist_ok=True)
    hit.write_text(json.dumps(data, indent=1))
    return data


# ---------------------------------------------------------------- documents

class Doc:
    """One PDF with its line index. Resolves quotes to lines and rectangles."""

    def __init__(self, case_dir, doc_id):
        stem = DOC_FILES[doc_id]
        self.doc_id = doc_id
        self.text = (case_dir / "text" / f"{stem}.lined.txt").read_text()
        index = json.loads((case_dir / "lines" / f"{stem}.lines.json").read_text())
        self.pages = {p["page"]: p["lines"] for p in index["pages"]}
        self.pdf = pymupdf.open(case_dir / f"{stem}.pdf")

    def parse_id(self, line_id):
        m = re.fullmatch(rf"{self.doc_id}-p(\d+)-L(\d+)", str(line_id).strip("[] "))
        if not m:
            return None
        page, line = int(m.group(1)), int(m.group(2))
        return (page, line) if any(l["line"] == line for l in self.pages.get(page, [])) else None

    def _find(self, page, quote, near_line):
        """Occurrence of quote on a page, as (start, end, offsets); the one closest to near_line."""
        lines = self.pages[page]
        joined, offsets = "", []
        for l in lines:
            offsets.append(len(joined))
            joined += l["text"] + " "
        best = None
        for m in re.finditer(re.escape(quote), joined):
            first = max(i for i, o in enumerate(offsets) if o <= m.start())
            dist = abs(lines[first]["line"] - near_line)
            if best is None or dist < best[0]:
                best = (dist, m.start(), m.end())
        return (best[1], best[2], offsets) if best else None

    def _rects(self, page, a, b, offsets):
        """One tight rectangle per line touched by characters [a, b) of the joined page text."""
        out = []
        for i, l in enumerate(self.pages[page]):
            lo, hi = max(a, offsets[i]), min(b, offsets[i] + len(l["text"]))
            if lo >= hi:
                continue
            part = l["text"][lo - offsets[i]: hi - offsets[i]].strip()
            x0, y0, x1, y1 = l["bbox"]
            hits = self.pdf[page - 1].search_for(part, clip=pymupdf.Rect(x0 - 2, y0 - 2, x1 + 2, y1 + 2))
            if hits:
                x0, x1 = min(h.x0 for h in hits), max(h.x1 for h in hits)
            out.append((l["line"], [round(v, 2) for v in (max(x0, l["bbox"][0]), y0, min(x1, l["bbox"][2]), y1)]))
        return out

    def locate(self, quote, line_id=None):
        """Verify a quote is verbatim and anchor it. Returns (span, start, offsets) or None."""
        quote = re.sub(r"\s+", " ", quote or "").strip()
        if not quote:
            return None
        cited = self.parse_id(line_id) if line_id else None
        order = ([cited[0]] if cited else []) + [p for p in self.pages if not cited or p != cited[0]]
        for page in order:
            hit = self._find(page, quote, cited[1] if cited and cited[0] == page else 0)
            if hit:
                a, b, offsets = hit
                rects = self._rects(page, a, b, offsets)
                span = {"doc_id": self.doc_id, "page": page, "line_start": rects[0][0],
                        "line_end": rects[-1][0], "rects": [r for _, r in rects]}
                return span, a, offsets
        return None

    def phrase_rects(self, span, start, offsets, quote, phrase):
        i = quote.find(phrase)
        return [r for _, r in self._rects(span["page"], start + i, start + i + len(phrase), offsets)]

    def lines_span(self, first_id, last_id):
        """A span covering whole lines, for policy clauses."""
        a, b = self.parse_id(first_id), self.parse_id(last_id)
        if not a or not b or a[0] != b[0] or a[1] > b[1]:
            return None
        ls = [l for l in self.pages[a[0]] if a[1] <= l["line"] <= b[1]]
        return {"doc_id": self.doc_id, "page": a[0], "line_start": a[1], "line_end": b[1],
                "rects": [l["bbox"] for l in ls]}, " ".join(l["text"] for l in ls)


# ---------------------------------------------------------------- numbers

WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve".split())}
DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")


def numbers(phrase):
    """Every number in a phrase: 'eight-week' -> 8, '$4,350' -> 4350, '4 weeks' -> 4."""
    phrase = DATE.sub(" ", phrase)
    out = [float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", phrase)]
    out += [float(WORDS[w]) for w in re.findall(r"[a-z]+", phrase.lower()) if w in WORDS]
    return out


def quantity(q, unit):
    """Read a quantity from the phrase the model pointed at. The model's own arithmetic is not trusted."""
    if not q or not q.get("phrase"):
        return None
    dates = [datetime(int(y), int(m), int(d)) for m, d, y in DATE.findall(q["phrase"])]
    if len(dates) == 2 and unit and unit.startswith(("week", "day", "month")):
        days = abs((dates[1] - dates[0]).days)
        return days // {"w": 7, "d": 1, "m": 30}[unit[0]]
    found = numbers(q["phrase"])
    if not found:
        return None
    value = q.get("value")
    n = value if isinstance(value, (int, float)) and float(value) in found else found[0]
    return int(n) if float(n).is_integer() else n


def money(n, unit):
    return f"${n:,}" if unit == "USD" else f"{n} {unit}"


# ---------------------------------------------------------------- stages

def stage_read(dl, pol):
    """Stage 1: requirements, grouped into the stated basis and alternative bases."""
    out = ask(prompts.READ.format(letter=dl.text, policy=pol.text))
    d = out["denial"]
    reason = dl.locate(d["reason_text"], d.get("line_start"))
    if not reason:
        sys.exit("stage 1: the denial reason is not verbatim in the letter")
    ref = dl.lines_span(d["policy_ref_line"], d["policy_ref_line"])
    denial = {"reason_text": re.sub(r"\s+", " ", d["reason_text"]).strip(), "category": d["category"],
              "source": reason[0],
              "policy_ref": {"policy_id": d["policy_id"], "title": d["policy_title"], "clause": d["clause"],
                             "source": ref[0]}}
    bases, alt = [], 0
    for b in out["bases"]:
        head = pol.lines_span(b["line_start"], b["line_end"])
        if not head:
            continue  # a basis the model cannot point to in the policy does not exist
        stated = b["kind"] == "stated"
        alt += 0 if stated else 1
        reqs = []
        for i, r in enumerate(b["requirements"], 1):
            src = pol.locate(r["policy_text"], r.get("line_start"))
            if not src:
                continue
            reqs.append({"req_id": f"{'R' if stated else 'A'}{i}", "clause": r["clause"], "text": r["text"],
                         "policy_source": src[0], "policy_text": re.sub(r"\s+", " ", r["policy_text"]).strip(),
                         "facets": r["facets"], "_label": r.get("short_label") or r["clause"],
                         "_threshold": r.get("threshold")})
        if reqs:
            bases.append({"basis_id": "STATED" if stated else f"ALT-{alt}", "kind": b["kind"], "title": b["title"],
                          "clause": b["clause"], "policy_source": head[0], "requirements": reqs})
    bases.sort(key=lambda b: b["kind"] != "stated")
    return denial, bases


def stage_match_verify(req, cr):
    """Stages 2 and 3 for one requirement: the model proposes passages, code keeps what it can confirm."""
    th = req.pop("_threshold")
    out = ask(prompts.MATCH.format(
        clause=req["clause"], policy_text=req["policy_text"], facets=json.dumps(req["facets"]),
        threshold=json.dumps(th) if th else "none", record=cr.text))
    evidence, near, quantities, seen = [], [], [], set()
    for c in out.get("candidates", []):
        hit = cr.locate(c.get("quote"), c.get("line_start"))
        if not hit:
            continue  # not verbatim anywhere in the record: dropped
        span, start, offsets = hit
        quote = re.sub(r"\s+", " ", c["quote"]).strip()
        where = (span["page"], span["line_start"], span["line_end"])
        if where in seen:
            continue
        seen.add(where)
        if c.get("relation") == "supports":
            eid = f"{req['req_id']}-E{len(evidence) + 1}"
            phrases = [{"text": k["text"], "facet": k["facet"],
                        "rects": cr.phrase_rects(span, start, offsets, quote, k["text"])}
                       for k in c.get("key_phrases", [])
                       if k.get("text") and k["text"] in quote and k.get("facet") in req["facets"]]
            evidence.append({"evidence_id": eid, "source": span, "quote": quote, "key_phrases": phrases,
                             "rationale": c.get("reason", "")})
            for field in ("found_quantity", "required_quantity"):
                q = c.get(field)
                if q and q.get("phrase") and q["phrase"] not in quote:
                    c[field] = None  # a quantity must be read from the quoted text
            if th and c.get("found_quantity"):
                quantities.append((eid, quantity(c["found_quantity"], th.get("unit")),
                                   quantity(c.get("required_quantity"), th.get("unit"))))
        elif c.get("relation") in ("insufficient", "off_target", "contradicts"):
            near.append({"source": span, "quote": quote, "relation": c["relation"], "why_not": c.get("reason", "")})

    check = None
    if th and evidence:
        eid, found, required_from_record = next((q for q in quantities if q[1] is not None),
                                                (evidence[0]["evidence_id"], None, None))
        required = th.get("value") if th.get("value") is not None else required_from_record
        if required is not None:
            op = "<=" if th.get("comparator", ">=").startswith("<") else ">="
            passed = found is not None and (found >= required if op == ">=" else found <= required)
            check = {"label": th.get("label") or req["text"], "comparator": op, "required": required,
                     "found": found, "unit": th.get("unit") or "", "passed": passed, "evidence_id": eid}

    covered = {k["facet"] for e in evidence for k in e["key_phrases"]}
    if evidence and covered >= set(req["facets"]) and (not check or check["passed"]):
        status = "supported"
    elif evidence:
        status = "partial"
    elif any(n["relation"] == "contradicts" for n in near):
        status = "contradicted"
    else:
        status = "missing"

    req.update(status=status, evidence=evidence, near_misses=near[:3])
    if check:
        req["quantity_check"] = check
    if status != "supported":
        gap = out.get("gap") or {}
        if check and not check["passed"] and check["found"] is not None:
            summary = f"{check['found']} of {check['required']} {check['unit']} documented."
        else:
            summary = gap.get("summary") or {"contradicted": "The record indicates otherwise."}.get(
                status, "No supporting passage anywhere in the record.")
        req["gap"] = {"summary": summary,
                      "what_would_satisfy": gap.get("what_would_satisfy") or f"Documentation that meets policy {req['clause']}.",
                      "suggested_action": gap.get("suggested_action") or "Obtain the missing documentation before appealing."}
    return req


def stage_decide(bases):
    """Stage 4: the recommendation follows from the statuses. No model involved."""
    for b in bases:
        counts = {s: sum(r["status"] == s for r in b["requirements"])
                  for s in ("supported", "partial", "missing", "contradicted")}
        counts["total"] = len(b["requirements"])
        b["counts"], b["supportable"] = counts, counts["supported"] == counts["total"]
    stated = bases[0]
    review = "Open each cited passage and confirm it says what the draft claims."
    last = "Approve, edit and submit; the system does not submit."
    if stated["supportable"]:
        n = stated["counts"]["total"]
        return {"type": "appeal_on_stated_basis", "basis_id": stated["basis_id"],
                "banner": f"All {n} requirements under {stated['clause']} are supported by the record. Ready for staff review.",
                "rationale": "Every criterion the denial relies on has a verified source passage. No alternative basis is needed.",
                "human_actions": [review, "Confirm the policy version in force on the denial date.", last]}
    gap = next(r for r in stated["requirements"] if r["status"] != "supported")
    word = "incomplete" if gap["status"] == "partial" else "missing"
    alt = next((b for b in bases[1:] if b["supportable"]), None)
    if alt:
        k = alt["counts"]["total"]
        title = alt["title"][0].lower() + alt["title"][1:]
        return {"type": "appeal_on_alternative_basis", "basis_id": alt["basis_id"],
                "banner": f"Evidence {word} for {gap['_label']} ({gap['clause']}). Recommend appealing under "
                          f"{alt['clause']}, {title}: {k} of {k} requirements supported.",
                "rationale": f"The denial rests on {gap['clause']}, which the record does not support. The same policy "
                             f"grants coverage under {alt['clause']}, and each of its requirements has a verified source passage.",
                "human_actions": [f"Confirm {alt['clause']} applies to this member's plan and was in force on the denial date.",
                                  review, f"Decide whether to also obtain documentation for {gap['clause']}.", last]}
    return {"type": "obtain_documentation", "basis_id": None,
            "banner": f"Evidence {word} for {gap['clause']}: {gap['gap']['summary']} No alternative basis is supported "
                      f"by this record. Obtain the missing documentation before appealing.",
            "rationale": "Neither the stated basis nor any alternative basis in the policy is fully supported by the record.",
            "human_actions": [r["gap"]["suggested_action"] for r in stated["requirements"] if r["status"] != "supported"]
                             + ["Do not submit an appeal until the gap is documented."]}


NUM = re.compile(r"\d+(?:[.,/]\d+)*")


def stage_draft(case, denial, bases, rec):
    """Stage 5: the model writes from verified evidence only; code re-checks every claim."""
    chosen = next((b for b in bases if b["basis_id"] == rec["basis_id"]), None)
    use = [chosen] + ([bases[0]] if chosen is not bases[0] else []) if chosen else bases[:1]
    ok_reqs = [r for b in use for r in b["requirements"] if r["status"] == "supported"]
    quotes = {e["evidence_id"]: e["quote"] for r in ok_reqs for e in r["evidence"]}
    facts = [{"clause": r["clause"], "requirement": r["text"],
              "evidence": [{"id": e["evidence_id"], "quote": e["quote"]} for e in r["evidence"]]} for r in ok_reqs]

    def problems(blocks):
        errs = []
        for i, b in enumerate(blocks):
            if b.get("type") != "claim":
                b["citations"] = []
                continue
            if not b.get("citations") or any(c not in quotes for c in b["citations"]):
                errs.append(f"block {i}: every claim must cite ids from the evidence list")
                continue
            cited = set(NUM.findall(" ".join(quotes[c] for c in b["citations"])))
            bad = [n for n in NUM.findall(b["text"]) if n not in cited]
            if bad:
                errs.append(f"block {i}: {bad} do not appear in the cited quotes; remove them or cite the passage that has them")
        return errs

    prompt = prompts.DRAFT.format(
        case=json.dumps({k: case[k] for k in ("case_id", "service_requested", "key_dates", "payer")}),
        denial=denial["reason_text"], policy=f"{denial['policy_ref']['policy_id']} {denial['policy_ref']['clause']}",
        basis=f"{chosen['clause']} ({chosen['title']})" if chosen else "none: only state what is supported",
        facts=json.dumps(facts, indent=1))
    blocks, errs = [], ["no draft yet"]
    for _ in range(3):
        blocks = ask(prompt)["blocks"]
        errs = problems(blocks)
        if not errs:
            break
        prompt += "\n\nYour previous draft was rejected:\n" + "\n".join(errs) + "\nReturn a corrected draft."
    if errs:  # fall back to sentences that are verbatim by construction
        blocks = [{"type": "claim", "text": f"The record states: \"{e['quote']}\"", "citations": [e["evidence_id"]]}
                  for r in ok_reqs for e in r["evidence"]]
    blocks = [{"type": b["type"], "text": b["text"], "citations": b["citations"]} for b in blocks]
    if not chosen:
        blocks = [b for b in blocks if b["type"] == "claim"]
        for r in bases[0]["requirements"]:
            if r["status"] != "supported":
                blocks.append({"type": "gap", "citations": [e["evidence_id"] for e in r["evidence"]],
                               "text": f"{r['clause']}: {r['gap']['summary']} This paragraph cannot be written until it is documented."})
    return {"basis_id": rec["basis_id"], "status": "ready_for_review" if chosen else "blocked_on_gaps", "blocks": blocks}


# ---------------------------------------------------------------- run

def run(case_dir):
    case = json.loads((case_dir / "case.json").read_text())
    dl, pol, cr = (Doc(case_dir, d) for d in ("DL", "POL", "CR"))
    denial, bases = stage_read(dl, pol)
    reqs = [r for b in bases for r in b["requirements"]]
    with ThreadPoolExecutor(8) as pool:
        list(pool.map(lambda r: stage_match_verify(r, cr), reqs))
    rec = stage_decide(bases)
    draft = stage_draft(case, denial, bases, rec)
    for r in reqs:
        r.pop("_label", None)
    analysis = {"schema_version": "1.0", "case_id": case["case_id"], "generated_by": f"pipeline ({MODEL})",
                "documents": case["documents"], "denial": denial, "bases": bases,
                "recommendation": rec, "draft": draft}

    # Last step: the validator. A run that fails verification writes no output.
    tmp = ROOT / "out" / f"{case['case_id']}.unverified.json"
    tmp.parent.mkdir(exist_ok=True)
    tmp.write_text(json.dumps(analysis, indent=1, ensure_ascii=False))
    result = subprocess.run([sys.executable, str(ROOT / "tools" / "validate_analysis.py"), str(case_dir), str(tmp)],
                            capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(f"{case['case_id']}: verification failed, nothing written (see {tmp})")
        return False
    out = case_dir / "analysis.json"
    tmp.replace(ROOT / "out" / f"{case['case_id']}.json")
    out.write_text(json.dumps(analysis, indent=1, ensure_ascii=False))
    print(f"{case['case_id']}: wrote {out.relative_to(ROOT)}")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("case_dir", type=Path, nargs="?")
    ap.add_argument("--all", action="store_true", help="run every case in data/cases")
    args = ap.parse_args()
    load_env()
    dirs = sorted(p.parent for p in (ROOT / "data" / "cases").glob("*/case.json")) if args.all else [args.case_dir]
    if not dirs or dirs[0] is None:
        ap.error("give a case directory or --all")
    sys.exit(0 if all([run(d.resolve()) for d in dirs]) else 1)


if __name__ == "__main__":
    main()
