#!/usr/bin/env python3
"""Regenerate the synthetic demo cases.

Reads the case definitions (case_a.py, case_b.py, case_c.py) and writes, for
each case, into data/cases/<case_id>/:

  denial_letter.pdf, policy.pdf, clinical_record.pdf   the source documents
  lines/<doc>.lines.json                               every numbered line: id, text, bbox
  text/<doc>.lined.txt                                 the same lines as "[LINE-ID] text"
  case.json                                            case metadata
  analysis.gold.json                                   the answer key, in the pipeline's output schema

Because the PDFs and the line index come from the same layout pass, every
citation in the answer key is exact by construction.

Usage:  python tools/generate/build_kit.py            (needs: pip install reportlab)
"""
import datetime as dt
import json
import re
import sys
from pathlib import Path

from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import case_a, case_b, case_c  # noqa: E402

OUT = HERE.parents[1] / "data" / "cases"

# ---- page geometry (PDF points; all stored coordinates use a TOP-LEFT origin) ----
PAGE_W, PAGE_H = 612.0, 792.0
X_TEXT = 76.0          # left edge of body text
X_NUM = 62.0           # right edge of the gutter line number
X_RIGHT = 548.0        # right edge of body text
SIZE = 10.0
LEAD = 13.6
Y_FIRST = 96.0         # baseline of the first body line
Y_LAST = 744.0         # last allowed baseline
F_BODY, F_HEAD = "Helvetica", "Helvetica-Bold"
BULLET_INDENT = 12.0
FOOTER = "SYNTHETIC DEMO DATA - fictional patient, provider, payer and policy. Not for clinical use."

MARK = re.compile(r"\[\[(/?)([a-z0-9_]+)\]\]")


def parse_markup(raw):
    """Strip [[id]]...[[/id]] markers. Returns (clean_text, {id: (start, end)})."""
    clean, spans, open_at, pos = [], {}, {}, 0
    n = 0
    for m in MARK.finditer(raw):
        chunk = raw[pos:m.start()]
        clean.append(chunk)
        n += len(chunk)
        closing, sid = m.group(1) == "/", m.group(2)
        if closing:
            spans[sid] = (open_at.pop(sid), n)
        else:
            assert sid not in open_at and sid not in spans, f"duplicate span {sid}"
            open_at[sid] = n
        pos = m.end()
    clean.append(raw[pos:])
    assert not open_at, f"unclosed spans {open_at}"
    text = "".join(clean)
    assert "  " not in text and text == text.strip(), f"whitespace problem in: {text!r}"
    return text, spans


def wrap(text, font, width):
    """Greedy word wrap. Returns [(start_offset, line_text)]; lines joined by ' ' equal text."""
    lines, cur, cur_start, pos = [], "", 0, 0
    for word in text.split(" "):
        trial = word if not cur else cur + " " + word
        if cur and stringWidth(trial, font, SIZE) > width:
            lines.append((cur_start, cur))
            cur, cur_start = word, pos
        else:
            cur = trial
        pos += len(word) + 1
    lines.append((cur_start, cur))
    return lines


def r2(x):
    return round(x, 2)


def layout_doc(doc_id, doc):
    """Lay out one document. Returns (pages, spans).

    pages: [[line dict]], spans: {span_id: {doc_id, page, line_start, line_end, text, block}}
    """
    pages, spans = [], {}
    for pno, blocks in enumerate(doc["pages"], start=1):
        y, lineno, lines, first = Y_FIRST, 0, [], True
        for blk in blocks:
            kind = blk[0]
            if kind == "sp":
                y += LEAD * 0.55
                continue
            raw = blk[1]
            indent = blk[2] if len(blk) > 2 else 0.0
            font = F_HEAD if kind == "h" else F_BODY
            if kind == "h" and not first:
                y += 5.0
            text, bspans = parse_markup(raw)
            hang = 0.0
            if kind == "b":
                text = "- " + text
                bspans = {k: (a + 2, b + 2) for k, (a, b) in bspans.items()}
                indent, hang = BULLET_INDENT, stringWidth("- ", font, SIZE)
            wrapped = wrap(text, font, X_RIGHT - X_TEXT - indent - hang)
            block_lines = []
            for i, (start, ltext) in enumerate(wrapped):
                lineno += 1
                x0 = X_TEXT + indent + (hang if i > 0 else 0.0)
                assert y <= Y_LAST, f"{doc_id} page {pno} overflows at: {ltext!r}"
                rec = {
                    "line_id": f"{doc_id}-p{pno}-L{lineno}", "page": pno, "line": lineno,
                    "text": ltext, "style": "heading" if kind == "h" else "body",
                    "_x0": x0, "_base": y, "_font": font, "_start": start,
                }
                rec["bbox"] = [r2(x0), r2(y - 8.8), r2(x0 + stringWidth(ltext, font, SIZE)), r2(y + 3.0)]
                lines.append(rec)
                block_lines.append(rec)
                y += LEAD
            y += 3.0
            first = False
            for sid, (a, b) in bspans.items():
                assert sid not in spans, f"span id reused: {sid}"
                cover = [l for l in block_lines if l["_start"] < b and l["_start"] + len(l["text"]) > a]
                spans[sid] = {
                    "doc_id": doc_id, "page": pno, "text": text[a:b], "a": a, "b": b,
                    "block_lines": block_lines,
                    "line_start": cover[0]["line"], "line_end": cover[-1]["line"],
                }
        pages.append(lines)
    return pages, spans


def rects_for(block_lines, a, b):
    """Tight rectangles (one per line) covering characters [a, b) of a block."""
    out = []
    for l in block_lines:
        s, e = l["_start"], l["_start"] + len(l["text"])
        la, lb = max(a, s) - s, min(b, e) - s
        if la >= lb:
            continue
        xa = l["_x0"] + stringWidth(l["text"][:la], l["_font"], SIZE)
        xb = l["_x0"] + stringWidth(l["text"][:lb], l["_font"], SIZE)
        out.append([r2(xa), r2(l["_base"] - 8.8), r2(xb), r2(l["_base"] + 3.0)])
    return out


def span_obj(sp):
    return {
        "doc_id": sp["doc_id"], "page": sp["page"],
        "line_start": sp["line_start"], "line_end": sp["line_end"],
        "rects": rects_for(sp["block_lines"], sp["a"], sp["b"]),
    }


def draw_pdf(path, doc, pages):
    c = canvas.Canvas(str(path), pagesize=(PAGE_W, PAGE_H))
    c.setTitle(f"{doc['title']} (synthetic)")
    c.setAuthor("Appealio demo kit")
    total = len(pages)
    for pno, lines in enumerate(pages, start=1):
        c.setFillGray(0.0)
        c.setFont(F_HEAD, 11.5)
        c.drawString(X_TEXT, PAGE_H - 46, doc["header"])
        c.setFont(F_BODY, 8.5)
        c.setFillGray(0.35)
        c.drawString(X_TEXT, PAGE_H - 60, doc["banner"])
        c.setStrokeGray(0.6)
        c.setLineWidth(0.6)
        c.line(X_TEXT, PAGE_H - 68, X_RIGHT, PAGE_H - 68)
        for l in lines:
            c.setFillGray(0.45)
            c.setFont(F_BODY, 7)
            c.drawRightString(X_NUM, PAGE_H - l["_base"], str(l["line"]))
            c.setFillGray(0.0)
            c.setFont(l["_font"], SIZE)
            c.drawString(l["_x0"], PAGE_H - l["_base"], l["text"])
        c.setFillGray(0.45)
        c.setFont(F_BODY, 7)
        c.drawString(X_TEXT, PAGE_H - 768, FOOTER)
        c.drawRightString(X_RIGHT, PAGE_H - 768, f"Page {pno} of {total}")
        c.showPage()
    c.save()


def public_line(l):
    return {k: l[k] for k in ("line_id", "line", "text", "style", "bbox")}


def resolve_gold(case, spans, docs_meta):
    g = case["gold"]

    def ev_text(sid):
        return spans[sid]["text"]

    den = g["denial"]
    analysis = {
        "schema_version": "1.0",
        "case_id": case["case_id"],
        "generated_by": "gold",
        "documents": docs_meta,
        "denial": {
            "reason_text": ev_text(den["reason_span"]),
            "category": den["category"],
            "source": span_obj(spans[den["reason_span"]]),
            "policy_ref": {
                "policy_id": den["policy_ref"]["policy_id"],
                "title": den["policy_ref"]["title"],
                "clause": den["policy_ref"]["clause"],
                "source": span_obj(spans[den["policy_ref"]["span"]]),
            },
        },
        "bases": [],
    }
    all_eids = set()
    for b in g["bases"]:
        reqs = []
        counts = {"supported": 0, "partial": 0, "missing": 0, "contradicted": 0}
        for r in b["requirements"]:
            evs = []
            for i, e in enumerate(r["evidence"], start=1):
                sp = spans[e["span"]]
                assert sp["doc_id"] == "CR", "evidence must come from the clinical record"
                kps = []
                for phrase, facet in e["key_phrases"]:
                    off = sp["text"].find(phrase)
                    assert off >= 0, f"key phrase not in span {e['span']}: {phrase!r}"
                    assert facet in r["facets"], f"unknown facet {facet} in {r['req_id']}"
                    kps.append({"text": phrase, "facet": facet,
                                "rects": rects_for(sp["block_lines"], sp["a"] + off, sp["a"] + off + len(phrase))})
                eid = f"{r['req_id']}-E{i}"
                all_eids.add(eid)
                evs.append({"evidence_id": eid, "source": span_obj(sp), "quote": sp["text"],
                            "key_phrases": kps, "rationale": e["rationale"]})
            nms = [{"source": span_obj(spans[n["span"]]), "quote": ev_text(n["span"]),
                    "relation": n["relation"], "why_not": n["why_not"]} for n in r["near_misses"]]
            req = {
                "req_id": r["req_id"], "clause": r["clause"], "text": r["text"],
                "policy_source": span_obj(spans[r["policy_span"]]),
                "policy_text": ev_text(r["policy_span"]),
                "facets": r["facets"], "status": r["status"],
                "evidence": evs, "near_misses": nms,
            }
            if "quantity_check" in r:
                q = dict(r["quantity_check"])
                q["evidence_id"] = f"{r['req_id']}-E{q.pop('evidence')}"
                assert q["evidence_id"] in all_eids
                ok = q["found"] >= q["required"] if q["comparator"] == ">=" else q["found"] <= q["required"]
                assert ok == q["passed"], f"quantity_check inconsistent in {r['req_id']}"
                req["quantity_check"] = q
            if "gap" in r:
                req["gap"] = r["gap"]
            assert (r["status"] == "supported") == (bool(evs) and "gap" not in r), r["req_id"]
            counts[r["status"]] += 1
            reqs.append(req)
        counts["total"] = len(reqs)
        analysis["bases"].append({
            "basis_id": b["basis_id"], "kind": b["kind"], "title": b["title"], "clause": b["clause"],
            "policy_source": span_obj(spans[b["policy_span"]]),
            "requirements": reqs, "counts": counts,
            "supportable": counts["supported"] == counts["total"],
        })
    rec = g["recommendation"]
    by_id = {b["basis_id"]: b for b in analysis["bases"]}
    if rec["basis_id"] is not None:
        assert by_id[rec["basis_id"]]["supportable"], "recommended basis must be fully supported"
    else:
        assert not any(b["supportable"] for b in analysis["bases"])
    analysis["recommendation"] = rec
    for blk in g["draft"]["blocks"]:
        for cid in blk["citations"]:
            assert cid in all_eids, f"draft cites unknown evidence {cid}"
        assert blk["type"] != "claim" or blk["citations"], "every claim needs a citation"
    analysis["draft"] = g["draft"]
    return analysis


def build_case(case):
    cdir = OUT / case["case_id"]
    (cdir / "lines").mkdir(parents=True, exist_ok=True)
    (cdir / "text").mkdir(parents=True, exist_ok=True)
    spans, docs_meta = {}, []
    for doc_id, doc in case["docs"].items():
        pages, dspans = layout_doc(doc_id, doc)
        assert not (set(spans) & set(dspans))
        spans.update(dspans)
        draw_pdf(cdir / doc["file"], doc, pages)
        stem = doc["file"][:-4]
        (cdir / "lines" / f"{stem}.lines.json").write_text(json.dumps({
            "doc_id": doc_id, "file": doc["file"], "title": doc["title"],
            "page_size": [PAGE_W, PAGE_H], "coord_origin": "top-left", "units": "pt",
            "pages": [{"page": i, "lines": [public_line(l) for l in ls]} for i, ls in enumerate(pages, start=1)],
        }, indent=1, ensure_ascii=False) + "\n")
        txt = []
        for i, ls in enumerate(pages, start=1):
            txt.append(f"=== {doc_id} | {doc['title']} | page {i} of {len(pages)} ===")
            txt.extend(f"[{l['line_id']}] {l['text']}" for l in ls)
            txt.append("")
        (cdir / "text" / f"{stem}.lined.txt").write_text("\n".join(txt))
        docs_meta.append({"doc_id": doc_id, "file": doc["file"], "title": doc["title"],
                          "pages": len(pages), "lines_file": f"lines/{stem}.lines.json",
                          "text_file": f"text/{stem}.lined.txt"})
    analysis = resolve_gold(case, spans, docs_meta)
    (cdir / "analysis.gold.json").write_text(json.dumps(analysis, indent=1, ensure_ascii=False) + "\n")
    meta = dict(case["meta"])
    kd = meta["key_dates"]
    due = dt.date.fromisoformat(kd["denial"]) + dt.timedelta(days=180)
    assert due.isoformat() == kd["appeal_deadline"], f"deadline should be {due}"
    (cdir / "case.json").write_text(json.dumps({
        "case_id": case["case_id"], **meta, "documents": docs_meta,
        "synthetic": True,
    }, indent=1, ensure_ascii=False) + "\n")
    return {
        "case_id": case["case_id"], "title": meta["title"], "scenario": meta["scenario"],
        "demo_role": meta["demo_role"], "one_line": meta["one_line"],
        "expected_recommendation": analysis["recommendation"]["type"],
        "expected_banner": analysis["recommendation"]["banner"],
        "path": f"cases/{case['case_id']}",
    }


def main():
    index = [build_case(m.CASE) for m in (case_a, case_b, case_c)]
    (OUT / "index.json").write_text(json.dumps({"cases": index}, indent=1, ensure_ascii=False) + "\n")
    for row in index:
        print(f"{row['case_id']}: {row['expected_recommendation']}")


if __name__ == "__main__":
    main()
