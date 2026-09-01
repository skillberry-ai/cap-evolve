#!/usr/bin/env python3
"""Label-safe TRUE redaction + replacement for PDF form values (PyMuPDF).

WHEN TO USE THIS
----------------
Use it ONLY for a value the instructions explicitly tell you to *redact / remove*
(e.g. masking a student ID to its last 4 digits). Do NOT use it to fix an ordinary
wrong value (name, email, date, phone) -- those only need a white COVER
(page.draw_rect) plus new text; leaving the old value extractable under the cover
is fine and is NOT a reason to redact.

WHY IT EXISTS
-------------
page.apply_redactions() deletes EVERY glyph whose box touches the redaction
rectangle. On real forms the value sits directly under (or beside) its label, so a
redaction rectangle that is padded/rounded upward by even 2-3 points silently
ERASES the label above it (e.g. "STUDENT PID#:"). That is the single most common
way a form edit fails a "labels must not be covered/removed" check.

This helper is deterministic and safe because it redacts the EXACT rectangle
returned by page.search_for(value) -- never padded or expanded -- so it removes
the value without reaching the neighbouring label, then re-inserts the replacement
text at the original baseline.

USAGE
-----
    python redact_value.py IN.pdf OUT.pdf "OLD=NEW" ["OLD2=NEW2" ...]

Each positional edit is OLD=NEW: OLD is searched literally on every page, the
matched glyphs are truly removed, and NEW (may be empty) is drawn at the same
spot. Example -- mask a student ID to its last 4 digits:
    python redact_value.py in.pdf out.pdf "A88888888=****5678"

You can also `from redact_value import redact_value` and call it directly.
"""
import sys

import fitz  # PyMuPDF


def redact_value(page, old, new, fontsize=11):
    """Truly redact every occurrence of `old` on `page` (label-safe) and draw
    `new` at the same position. Returns the number of occurrences handled.

    Uses the UNMODIFIED rect from page.search_for(old) -- never padded upward --
    so apply_redactions() cannot reach the label sitting above the value."""
    rects = page.search_for(old)
    baselines = [(r.x0, r.y1 - 2) for r in rects]
    for r in rects:
        # WHITE fill (never black); exact rect, never enlarged.
        page.add_redact_annot(r, fill=(1, 1, 1))
    if rects:
        page.apply_redactions()
        if new:
            for (x, y) in baselines:
                page.insert_text((x, y), new, fontsize=fontsize, color=(0, 0, 0))
    return len(rects)


def main(argv):
    if len(argv) < 4:
        print(__doc__)
        return 1
    in_pdf, out_pdf = argv[1], argv[2]
    edits = []
    for spec in argv[3:]:
        if "=" not in spec:
            print(f"Skipping malformed edit (need OLD=NEW): {spec!r}")
            continue
        old, new = spec.split("=", 1)
        edits.append((old, new))

    doc = fitz.open(in_pdf)
    total = 0
    for page in doc:
        for old, new in edits:
            total += redact_value(page, old, new)
    doc.save(out_pdf)
    doc.close()
    print(f"Redacted {total} occurrence(s) -> {out_pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
