#!/usr/bin/env python3
"""Derive the E26-nohist optimizer INSTRUCTIONS from an E20 INSTRUCTIONS.md: delete every pointer to the
cross-iteration history (LEDGER, JOURNAL, RUNMAP, prior_iterations, insights). Nothing else changes.
usage: nohist_instructions.py <E20 INSTRUCTIONS.md> <out>"""
import re, sys
src = open(sys.argv[1]).read()
s = src
def cut(pattern, repl="", flags=re.S):
    global s
    n = len(re.findall(pattern, s, flags))
    assert n == 1, (pattern[:50], n)
    s = re.sub(pattern, repl, s, flags=flags)
cut(r"\nanything `LEDGER.md` / `JOURNAL.md` show was already tried and rejected\.", "")
cut(r"- `\./LEDGER\.md` — FACTS.*?(?=- `\./PROCESS\.md`)", "")
cut(r"1\. Read your capability SKILL\(s\) \+ the diagnose method \+ the cross-iteration files\n   \(LEDGER facts, JOURNAL handover, RUNMAP for clusters you'll touch\)\.", "1. Read your capability SKILL(s) + the diagnose method.")
cut(r"5\. Fill `PROCESS\.md` and APPEND your entry to `JOURNAL\.md`\. STOP\.", "5. Fill `PROCESS.md`. STOP.")
cut(r"- \*\*JOURNAL\.md\*\* \(append ONE entry.*?(?=\n\{\{FAILURES\}\})", "")
cut(r"speculative/cosmetic edits or re-add anything already rejected \(check LEDGER/JOURNAL\)\.", "speculative/cosmetic edits.")
cut(r"PROCESS\.md \+ JOURNAL\.md are filled", "PROCESS.md is filled")
bad = re.findall(r"(?i)ledger|journal|runmap|prior_iterations|insights", s)
assert not bad, bad
open(sys.argv[2], "w").write(s)
print("ok", len(src), "->", len(s))
