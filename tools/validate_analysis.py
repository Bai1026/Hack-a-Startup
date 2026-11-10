#!/usr/bin/env python3
"""Verify an analysis JSON against the source documents, and score it against the answer key.

    python tools/validate_analysis.py data/cases/B-3117                      # checks the answer key itself
    python tools/validate_analysis.py data/cases/B-3117 out/B-3117.json      # checks and scores pipeline output
    python tools/validate_analysis.py data/cases/B-3117 out/B-3117.json --json

Part 1, verification (hard failures, exit code 1). These are the guarantees the
product makes, so the same checks belong inside the pipeline:
  - the file matches data/schema/analysis.schema.json (when jsonschema is installed)
  - every cited page and line exists
  - every quote is verbatim text from the lines it cites
  - every key phrase is a verbatim substring of its quote
  - every highlight rectangle sits on a cited line
  - statuses, counts and the recommendation follow the deterministic rules
  - every claim in the draft cites verified evidence for a supported requirement
  - every number or date in a claim appears in one of the quotes it cites

Part 2, scoring against analysis.gold.json (reported, never fails the run):
  status accuracy, evidence recall and precision by line overlap, distractor
  hits, and whether the recommendation matches.

Standard library only; jsonschema is optional.
"""
import argparse
import json
import re
import sys
from pathlib import Path

SOURCE_DOCS = {"DL", "POL"}  # evidence must come from the record, never from these
NUM = re.compile(r"\d+(?:[.,/]\d+)*")  # 8, 4,350, 10/01/2026


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def load_lines(case_dir, documents):
    """{doc_id: {page: {line_no: line dict}}}"""
    out = {}
    for d in documents:
        lf = d.get("lines_file") or f"lines/{Path(d['file']).stem}.lines.json"
        data = json.loads((case_dir / lf).read_text())
        out[d["doc_id"]] = {p["page"]: {l["line"]: l for l in p["lines"]} for p in data["pages"]}
    return out


class Checker:
    def __init__(self, lines):
        self.lines, self.errors = lines, []

    def err(self, where, msg):
        self.errors.append(f"{where}: {msg}")

    def span_lines(self, span, where):
        page = self.lines.get(span["doc_id"], {}).get(span["page"])
        if page is None:
            self.err(where, f"no such page {span['doc_id']} p{span['page']}")
            return None
        if span["line_start"] > span["line_end"]:
            self.err(where, "line_start is after line_end")
            return None
        got = []
        for n in range(span["line_start"], span["line_end"] + 1):
            if n not in page:
                self.err(where, f"no such line {span['doc_id']}-p{span['page']}-L{n}")
                return None
            got.append(page[n])
        return got

    def verbatim(self, span, quote, where):
        ls = self.span_lines(span, where)
        if ls is None:
            return
        joined = norm(" ".join(l["text"] for l in ls))
        if norm(quote) not in joined:
            self.err(where, f"quote is not verbatim in the cited lines: {quote[:70]!r}")
        self.rects(span.get("rects", []), ls, where)

    def rects(self, rects, ls, where, tol=4.0):
        for r in rects:
            ok = any(l["bbox"][1] - tol <= r[1] and r[3] <= l["bbox"][3] + tol
                     and l["bbox"][0] - tol <= r[0] and r[2] <= l["bbox"][2] + tol for l in ls)
            if not ok:
                self.err(where, f"highlight rectangle {r} is not on a cited line")


def expected_recommendation(bases):
    stated = [b for b in bases if b["kind"] == "stated"]
    if stated and all(b["supportable"] for b in stated):
        return "appeal_on_stated_basis", stated[0]["basis_id"]
    for b in bases:
        if b["kind"] == "alternative" and b["supportable"]:
            return "appeal_on_alternative_basis", b["basis_id"]
    return "obtain_documentation", None


def verify(a, case_dir, schema_path):
    try:
        import jsonschema
        schema = json.loads(schema_path.read_text())
        schema_errors = [f"schema: {'/'.join(map(str, e.absolute_path))}: {e.message}"
                         for e in jsonschema.Draft202012Validator(schema).iter_errors(a)]
        schema_note = "schema checked"
    except ImportError:
        schema_errors, schema_note = [], "schema NOT checked (pip install jsonschema)"
    if schema_errors:
        return schema_errors, schema_note

    c = Checker(load_lines(case_dir, a["documents"]))
    c.verbatim(a["denial"]["source"], a["denial"]["reason_text"], "denial")
    c.span_lines(a["denial"]["policy_ref"]["source"], "denial.policy_ref")

    ev_status, ev_quote = {}, {}
    for b in a["bases"]:
        counts = {"supported": 0, "partial": 0, "missing": 0, "contradicted": 0}
        for r in b["requirements"]:
            w = f"{b['basis_id']}/{r['req_id']}"
            c.verbatim(r["policy_source"], r["policy_text"], w + " policy")
            for e in r["evidence"]:
                we = f"{w}/{e['evidence_id']}"
                if e["evidence_id"] in ev_status:
                    c.err(we, "duplicate evidence_id")
                ev_status[e["evidence_id"]] = r["status"]
                ev_quote[e["evidence_id"]] = e["quote"]
                if e["source"]["doc_id"] in SOURCE_DOCS:
                    c.err(we, "evidence must come from the clinical record")
                c.verbatim(e["source"], e["quote"], we)
                ls = c.span_lines(e["source"], we) or []
                for k in e["key_phrases"]:
                    if k["text"] not in e["quote"]:
                        c.err(we, f"key phrase is not in the quote: {k['text']!r}")
                    if k["facet"] not in r["facets"]:
                        c.err(we, f"unknown facet {k['facet']!r}")
                    c.rects(k["rects"], ls, we + " key phrase")
            for i, n in enumerate(r["near_misses"]):
                c.verbatim(n["source"], n["quote"], f"{w}/near_miss[{i}]")
            st, q = r["status"], r.get("quantity_check")
            if q:
                want = None if q["found"] is None else (
                    q["found"] >= q["required"] if q["comparator"] == ">=" else q["found"] <= q["required"])
                if want is not None and want != q["passed"]:
                    c.err(w, "quantity_check.passed does not match the numbers")
                if q["evidence_id"] not in {e["evidence_id"] for e in r["evidence"]}:
                    c.err(w, "quantity_check points at evidence that is not on this requirement")
            if st == "supported":
                if not r["evidence"]:
                    c.err(w, "supported, but no evidence")
                if q and not q["passed"]:
                    c.err(w, "supported, but the quantity check failed")
                if "gap" in r:
                    c.err(w, "supported requirements have no gap")
            else:
                if "gap" not in r:
                    c.err(w, f"{st} requirements need a gap")
                if st == "missing" and r["evidence"]:
                    c.err(w, "missing, but evidence is listed (use partial)")
                if st == "partial" and not r["evidence"]:
                    c.err(w, "partial, but no evidence (use missing)")
                if st == "contradicted" and not any(n["relation"] == "contradicts" for n in r["near_misses"]):
                    c.err(w, "contradicted, but no contradicting passage is cited")
            counts[st] += 1
        counts["total"] = len(b["requirements"])
        if b["counts"] != counts:
            c.err(b["basis_id"], f"counts should be {counts}")
        if b["supportable"] != (counts["supported"] == counts["total"]):
            c.err(b["basis_id"], "supportable does not match the requirement statuses")

    rec = a["recommendation"]
    want = expected_recommendation(a["bases"])
    if (rec["type"], rec["basis_id"]) != want:
        c.err("recommendation", f"should be {want}")

    d = a["draft"]
    for i, blk in enumerate(d["blocks"]):
        w = f"draft.blocks[{i}]"
        for cid in blk["citations"]:
            if cid not in ev_status:
                c.err(w, f"cites unknown evidence {cid}")
            elif blk["type"] == "claim" and ev_status[cid] != "supported":
                c.err(w, f"claim cites {cid}, whose requirement is {ev_status[cid]}")
        if blk["type"] == "claim" and not blk["citations"]:
            c.err(w, "claim without a citation")
        if blk["type"] == "claim":
            cited = set(NUM.findall(" ".join(ev_quote.get(cid, "") for cid in blk["citations"])))
            for num in NUM.findall(blk["text"]):
                if num not in cited:
                    c.err(w, f"number {num!r} does not appear in any cited quote")
    if (d["status"] == "ready_for_review") != (rec["basis_id"] is not None):
        c.err("draft", "status must be ready_for_review exactly when a basis is recommended")
    if d["basis_id"] != rec["basis_id"]:
        c.err("draft", "basis_id must equal recommendation.basis_id")
    return c.errors, schema_note


def overlaps(s1, s2):
    return (s1["doc_id"], s1["page"]) == (s2["doc_id"], s2["page"]) and \
        s1["line_start"] <= s2["line_end"] and s2["line_start"] <= s1["line_end"]


def score(pred, gold):
    def by_clause(a):
        return {norm(r["clause"]): (b, r) for b in a["bases"] for r in b["requirements"]}
    P, G = by_clause(pred), by_clause(gold)
    rows, status_ok, g_hit, g_tot, p_hit, p_tot, distract = [], 0, 0, 0, 0, 0, 0
    for clause, (_, gr) in G.items():
        pr = P.get(clause, (None, None))[1]
        g_ev = [e["source"] for e in gr["evidence"]]
        g_nm = [n["source"] for n in gr["near_misses"]]
        p_ev = [e["source"] for e in pr["evidence"]] if pr else []
        hit = sum(any(overlaps(g, p) for p in p_ev) for g in g_ev)
        good = sum(any(overlaps(p, g) for g in g_ev) for p in p_ev)
        dis = sum((not any(overlaps(p, g) for g in g_ev)) and any(overlaps(p, n) for n in g_nm) for p in p_ev)
        ok = bool(pr) and pr["status"] == gr["status"]
        status_ok += ok
        g_hit += hit; g_tot += len(g_ev); p_hit += good; p_tot += len(p_ev); distract += dis
        rows.append({"clause": clause, "gold_status": gr["status"],
                     "pred_status": pr["status"] if pr else "(requirement not extracted)",
                     "status_ok": ok, "gold_evidence_found": f"{hit}/{len(g_ev)}",
                     "pred_evidence_correct": f"{good}/{len(p_ev)}", "distractor_hits": dis})
    gb = {b["basis_id"]: b["clause"] for b in gold["bases"]}
    pb = {b["basis_id"]: b["clause"] for b in pred["bases"]}
    gr_, pr_ = gold["recommendation"], pred["recommendation"]
    rec_ok = gr_["type"] == pr_["type"] and norm(gb.get(gr_["basis_id"], "")) == norm(pb.get(pr_["basis_id"], ""))
    return {
        "requirements": rows,
        "extra_requirements": sorted(set(P) - set(G)),
        "status_accuracy": round(status_ok / len(G), 3),
        "evidence_recall": round(g_hit / g_tot, 3) if g_tot else 1.0,
        "evidence_precision": round(p_hit / p_tot, 3) if p_tot else 1.0,
        "distractor_hits": distract,
        "recommendation_ok": rec_ok,
        "gold_recommendation": gr_["type"], "pred_recommendation": pr_["type"],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("case_dir", type=Path)
    ap.add_argument("analysis", type=Path, nargs="?")
    ap.add_argument("--json", action="store_true", help="print a JSON report")
    args = ap.parse_args()
    gold_path = args.case_dir / "analysis.gold.json"
    path = args.analysis or gold_path
    a = json.loads(path.read_text())
    schema_path = Path(__file__).resolve().parents[1] / "data" / "schema" / "analysis.schema.json"
    errors, note = verify(a, args.case_dir, schema_path)
    report = {"file": str(path), "verified": not errors, "errors": errors, "schema": note}
    if not errors and path.resolve() != gold_path.resolve():
        report["score"] = score(a, json.loads(gold_path.read_text()))
    if args.json:
        print(json.dumps(report, indent=1))
    else:
        print(f"{path}  [{note}]")
        if errors:
            print(f"  VERIFICATION FAILED, {len(errors)} problem(s):")
            for e in errors:
                print("   -", e)
        else:
            print("  verification passed: every quote, key phrase, highlight and citation checks out")
        if "score" in report:
            s = report["score"]
            print(f"  status accuracy {s['status_accuracy']}  evidence recall {s['evidence_recall']}  "
                  f"precision {s['evidence_precision']}  distractor hits {s['distractor_hits']}  "
                  f"recommendation {'ok' if s['recommendation_ok'] else 'WRONG'}")
            for r in s["requirements"]:
                flag = "ok " if r["status_ok"] else "BAD"
                print(f"   {flag} {r['clause']:9} gold={r['gold_status']:12} pred={r['pred_status']:12} "
                      f"found {r['gold_evidence_found']}  correct {r['pred_evidence_correct']}  "
                      f"distractors {r['distractor_hits']}")
            if s["extra_requirements"]:
                print("   requirements not in the answer key:", ", ".join(s["extra_requirements"]))
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
