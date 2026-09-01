#!/usr/bin/env python3
"""
True PDF redaction: permanently REMOVE text from the PDF content stream so it
can no longer be extracted (by pdftotext, pypdf, PyMuPDF get_text, or OCR of the
rendered page). Optionally draw replacement text where the original text was.

WHY THIS EXISTS
---------------
Drawing a rectangle, a white box, or an annotation *over* text does NOT remove it.
The characters stay in the content stream and every text-extraction tool (and any
verifier that greps the extracted text) still sees them. To actually redact you
must delete the underlying glyphs. PyMuPDF's redaction annotations + apply_redactions()
do exactly this. This script wraps that flow and never touches surrounding labels.

USAGE
-----
    python scripts/redact.py <input.pdf> <output.pdf> --spec spec.json

spec.json format (all keys optional):
    {
      "redact":  ["A12345678", "jinya@gmail.com", "Yaya"],   # exact strings to delete everywhere
      "regex":   ["\\bA\\d{8}\\b"],                            # regex patterns to delete everywhere
      "keep":    ["Lin et al."],                              # never redact these (e.g. self-citations)
      "replace": [                                             # after deleting, write new text in place
          {"find": "Yaya", "text": "Jinya Jiang"},
          {"find": "A12345678", "text": "****5678"}
      ],
      "fill": [1, 1, 1],          # redaction box color, default white (1,1,1). Use [0,0,0] for black bars.
      "scrub_metadata": false     # also clear document + XMP metadata (for anonymization tasks)
    }

You may instead pass terms directly:
    python scripts/redact.py in.pdf out.pdf --terms "A12345678" "jinya@gmail.com"

After running, the script re-opens the output and PRINTS a verification report:
which requested terms/patterns still appear in the extracted text (should be none,
except any listed under "keep").
"""
import argparse
import json
import re
import sys

import fitz  # PyMuPDF


def _rects_for_term(page, term):
    """All rectangles matching a literal term on a page."""
    return list(page.search_for(term)) if term else []


def _rects_for_regex(page, pattern):
    """Rectangles matching a regex, found via word geometry."""
    rects = []
    words = page.get_text("words")  # (x0,y0,x1,y1,"word",block,line,word_no)
    for w in words:
        if re.search(pattern, w[4]):
            rects.append(fitz.Rect(w[:4]))
    # Also try matching against the whole page text spans (multi-word matches)
    full = page.get_text()
    for m in re.finditer(pattern, full):
        for r in page.search_for(m.group(0)):
            rects.append(r)
    return rects


def redact(inp, out, spec):
    terms = list(spec.get("redact", []))
    regexes = list(spec.get("regex", []))
    keep = list(spec.get("keep", []))
    replaces = list(spec.get("replace", []))
    fill = tuple(spec.get("fill", [1, 1, 1]))
    scrub = bool(spec.get("scrub_metadata", False))

    doc = fitz.open(inp)
    # Remember where each replacement anchor was, per page, before redacting.
    replace_points = []  # (page_index, x, y, text)
    for page in doc:
        for rep in replaces:
            for r in page.search_for(rep["find"]):
                # baseline just inside the original rect
                replace_points.append((page.number, r.x0, r.y1 - 2, rep["text"]))

    for page in doc:
        keep_rects = []
        for k in keep:
            keep_rects.extend(_rects_for_term(page, k))

        target_rects = []
        for t in terms:
            target_rects.extend(_rects_for_term(page, t))
        for pat in regexes:
            target_rects.extend(_rects_for_regex(page, pat))

        for r in target_rects:
            if any(r.intersects(kr) and r in kr for kr in keep_rects):
                continue
            # Skip if this rect is fully inside a keep rect (self-citation etc.)
            if any(kr.contains(r) for kr in keep_rects):
                continue
            page.add_redact_annot(r, fill=fill)
        # Remove glyphs but leave images/vector labels intact.
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

    # Write replacement text where originals were removed.
    for pno, x, y, text in replace_points:
        doc[pno].insert_text(fitz.Point(x, y), text, fontname="helv", fontsize=11)

    if scrub:
        try:
            doc.set_metadata({})
        except Exception:
            pass
        try:
            doc.del_xml_metadata()
        except Exception:
            pass

    doc.save(out, garbage=4, deflate=True)
    doc.close()


def verify(out, spec):
    terms = list(spec.get("redact", []))
    regexes = list(spec.get("regex", []))
    keep = set(spec.get("keep", []))
    doc = fitz.open(out)
    text = "\n".join(p.get_text() for p in doc)
    doc.close()
    leaked = []
    for t in terms:
        if t in keep:
            continue
        if t and t in text:
            leaked.append(t)
    for pat in regexes:
        if re.search(pat, text):
            leaked.append(f"/{pat}/")
    if leaked:
        print("WARNING: these terms still appear in extracted text:", leaked, file=sys.stderr)
    else:
        print("OK: no redacted term found in extracted text.")
    return not leaked


def main():
    ap = argparse.ArgumentParser(description="Permanently remove text from a PDF.")
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--spec", help="Path to JSON spec (see module docstring).")
    ap.add_argument("--terms", nargs="*", default=[], help="Exact strings to redact.")
    ap.add_argument("--regex", nargs="*", default=[], help="Regex patterns to redact.")
    ap.add_argument("--black", action="store_true", help="Use black bars instead of white fill.")
    ap.add_argument("--scrub-metadata", action="store_true")
    args = ap.parse_args()

    spec = {}
    if args.spec:
        with open(args.spec) as f:
            spec = json.load(f)
    if args.terms:
        spec.setdefault("redact", []).extend(args.terms)
    if args.regex:
        spec.setdefault("regex", []).extend(args.regex)
    if args.black:
        spec["fill"] = [0, 0, 0]
    if args.scrub_metadata:
        spec["scrub_metadata"] = True

    redact(args.input, args.output, spec)
    ok = verify(args.output, spec)
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
