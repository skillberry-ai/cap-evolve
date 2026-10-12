#!/usr/bin/env python3
"""Warn about typed copies of MOCK outcome values in the prose.

Mock numbers (paper/results_data.json, numbers_pending.json) must reach the text only through \\pend macros, so that a final
build with \\draftmodefalse fails on them. This check finds the other leak: a mock value typed by hand into a section or
appendix file. It compares decimals, "N of M" and "N/M" fractions, and three-digit counts in the prose with the current mock
outcome values. It is a warning in draft mode (called from check_paper.py) and does nothing when the data are real.

Usage: python3 -I scripts/check_mock_leaks.py     (exit 0 always; prints one line per suspect)
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DESIGN = re.compile(r"^mock(T|Trials|Seeds|Bstar)[A-E]?$|^mockD(Tasks|Trials|Heldout)$")
# numbers that are protocol constants or known coincidences, not mock outcomes
ALLOW_NUM = {0.05, 0.01, 0.001, 0.1, 0.5, 0.9, 0.95, 0.8, 1.0, 2.0, 1.282, 1.645, 0.02, 0.2, 0.25, 0.75, 1.5, 3.0, 4.1, 4.6, 7.1, 8.6, 6.7, 40.0, 25.8}
CONTEXT_SKIP = re.compile(r"(Section|Table|Figure|Appendix|GPT-|Opus |Sonnet |LibreOffice |version |v)~?\s*$")
# (file name, token) pairs checked by hand and known to be coincidences with a mock value
ALLOW_FILE_TOKEN = {("v2_evaluation.tex", "0.6"), ("v2_setup.tex", "0.6"), ("config.tex", "0.7"), ("deviations_table.tex", "0.7"),
                    ("protocol.tex", "0.6"), ("protocol.tex", "5.5"), ("protocol.tex", "2.5")}
SCAN = ["sections/*.tex", "appendix/*.tex", "paper.tex"]
SKIP_FILES = {"results.tex", "config_generated.tex", "sim_table.tex"}


def mock_values():
    d = json.loads((ROOT / "results_data.json").read_text())
    if d.get("source") != "mock":
        return None
    m = json.loads((ROOT / "numbers_pending.json").read_text())
    nums, fracs, counts = set(), set(), set()
    for k, v in m.items():
        if DESIGN.match(k):
            continue
        v = v.replace("$-$", "-").replace("$<$", "").replace("$", "")
        if re.fullmatch(r"[+-]?\d+\.\d+", v):
            nums.add(abs(float(v)))
        elif re.fullmatch(r"\d+ of \d+", v):
            fracs.add(v)
        elif re.fullmatch(r"\d+/\d+", v):
            fracs.add(v.replace("/", " of "))
        elif re.fullmatch(r"\d{3,}", v):
            counts.add(int(v))
    return nums, fracs, counts


def strip(line: str) -> str:
    line = re.sub(r"(?<!\\)%.*", "", line)
    line = re.sub(r"\\(?:mock|sim|hist|cost|mde|null|st|err|real)[A-Za-z]*(\{\})?", " ", line)
    line = re.sub(r"\\(?:label|ref|cite[a-z]*|citep|citet|input|includegraphics|texttt|url)\*?(\[[^\]]*\])?\{[^}]*\}", " ", line)
    return line


def allowed(f, tok):
    return (f.name, tok.lstrip("+-")) in ALLOW_FILE_TOKEN


def leaks():
    vals = mock_values()
    if vals is None:
        return []
    nums, fracs, counts = vals
    out = []
    for pat in SCAN:
        for f in sorted(ROOT.glob(pat)):
            if f.name in SKIP_FILES:
                continue
            for i, raw in enumerate(f.read_text().split("\n"), 1):
                line = strip(raw)
                for m in re.finditer(r"(?<![\w.])([+-]?\d+\.\d+)(?![\w])", line):
                    x = abs(float(m.group(1)))
                    if x in nums and x not in ALLOW_NUM and not CONTEXT_SKIP.search(line[: m.start()]) and not allowed(f, m.group(1)):
                        out.append((f.relative_to(ROOT), i, m.group(1)))
                for m in re.finditer(r"\b(\d+) of (\d+)\b", line):
                    if m.group(0) in fracs:
                        out.append((f.relative_to(ROOT), i, m.group(0)))
                for m in re.finditer(r"\b(\d+)/(\d+)\b", line):
                    if f"{m.group(1)} of {m.group(2)}" in fracs and int(m.group(2)) > 10:
                        out.append((f.relative_to(ROOT), i, m.group(0)))
                for m in re.finditer(r"(?<![\w.,])(\d{3,})(?![\w.,])", line):
                    if int(m.group(1)) in counts and int(m.group(1)) not in (200, 250, 300, 350, 400, 550, 600):
                        out.append((f.relative_to(ROOT), i, m.group(1)))
    return out


def main() -> int:
    hits = leaks()
    for f, i, tok in hits[:20]:
        print(f"{f}:{i}: {tok}")
    print(f"{len(hits)} possible typed mock value(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
