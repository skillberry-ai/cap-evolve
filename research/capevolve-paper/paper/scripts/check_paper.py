#!/usr/bin/env python3
"""Pre-submission checks. Usage: python3 -I scripts/check_paper.py paper.pdf

Fails on: body over 10 pages, '??' in text, surviving \\pend (prints [[PEND]]
when draft mode is off), em dashes or '---' in .tex files, banned words,
undefined references or citations in the log. Reports draft flags, overfull boxes.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

PAGE_LIMIT = 10
ROOT = pathlib.Path(__file__).resolve().parent.parent
BANNED = [
    r"\bdelve", r"\bleverag", r"(?<!cluster-)\brobust", r"\bseamless", r"\bcrucial", r"\bpivotal",
    r"\blandscape", r"\btapestry", r"\brealm", r"\bunderscor", r"\bshowcas",
    r"\bunlock", r"in today's", r"it is worth noting", r"\bnotably",
    r"^\s*furthermore", r"\bmoreover", r"not only .{0,80} but also",
]
LABEL_RE = re.compile(r"\\newlabel\{paper:endofbody\}\{\{[^}]*\}\{(\d+)\}", re.DOTALL)


def tex_files():
    out = [ROOT / "paper.tex"]
    for d in ("sections", "appendix"):
        out += sorted((ROOT / d).glob("*.tex"))
    return out


def main() -> int:
    pdf = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "paper.pdf"
    if not pdf.exists():
        print(f"FAIL  no such PDF: {pdf}")
        return 2
    fails = 0
    text = subprocess.run(["pdftotext", "-layout", str(pdf), "-"],
                          capture_output=True, text=True).stdout
    total = text.count("\f")
    aux = pdf.with_suffix(".aux")
    body = total
    if aux.exists():
        m = LABEL_RE.search(aux.read_text(errors="replace"))
        if m:
            body = int(m.group(1))
    if body > PAGE_LIMIT:
        print(f"FAIL  body is {body} pages (limit {PAGE_LIMIT}, total {total})")
        fails += 1
    else:
        print(f"ok    body {body}/{PAGE_LIMIT} pages (total {total})")

    if "??" in text:
        print("FAIL  '??' in rendered text (undefined ref, cite or macro)")
        fails += 1
    n_pend_pdf = text.count("[[PEND]]")
    if n_pend_pdf:
        print(f"FAIL  {n_pend_pdf} surviving \\pend value(s) with draft mode off")
        fails += 1

    src = (ROOT / "paper.tex").read_text()
    draft_on = bool(re.search(r"^\s*\\draftmodetrue", src, re.M))
    n_needs = n_pend = n_prov = 0
    for f in tex_files() + [ROOT / "numbers_pending.tex"]:
        if not f.exists():
            continue
        s = f.read_text()
        code = "\n".join(l.split("%")[0] if not l.lstrip().startswith("%") else "" for l in s.splitlines())
        if "\u2014" in code or "---" in code:
            print(f"FAIL  em dash in {f.name}")
            fails += 1
        for pat in BANNED:
            for mm in re.finditer(pat, code, re.I | re.M):
                print(f"FAIL  banned phrase {mm.group(0)!r} in {f.name}")
                fails += 1
        n_needs += len(re.findall(r"\\needs\{", code))
        n_prov += len(re.findall(r"\\prov\{", code))
        if f.name != "numbers_pending.tex":
            n_pend += len(re.findall(r"\\pend\{", code))
    pending_defs = ROOT / "numbers_pending.tex"
    n_pend_uses = 0
    if pending_defs.exists():
        names = re.findall(r"\\newcommand\{\\(\w+)\}", pending_defs.read_text())
        for f in tex_files():
            body_src = f.read_text()
            for n in names:
                n_pend_uses += len(re.findall(r"\\" + n + r"(?![A-Za-z])", body_src))
    print(f"info  draft mode {'ON' if draft_on else 'off'}: {n_needs} \\needs, "
          f"{n_pend} inline \\pend, {n_pend_uses} uses of pending macros, {n_prov} \\prov")
    if not draft_on and (n_needs or n_pend or n_pend_uses):
        print("FAIL  draft mode off but \\needs/\\pend remain in the source")
        fails += 1

    log = pdf.with_suffix(".log")
    if log.exists():
        lg = log.read_text(errors="replace")
        und = re.findall(r"(?:Reference|Citation) `([^']+)' on page", lg)
        if und:
            print(f"FAIL  undefined refs/cites: {sorted(set(und))[:8]}")
            fails += 1
        ov = len(re.findall(r"Overfull \\[hv]box", lg))
        print(f"{'warn' if ov else 'ok  '}  {ov} overfull box(es)")
    print("FAILED" if fails else "PASSED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
