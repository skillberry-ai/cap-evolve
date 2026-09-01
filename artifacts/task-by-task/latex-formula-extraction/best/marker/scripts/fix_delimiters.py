#!/usr/bin/env python3
r"""Repair MISMATCHED ``\left..\right`` delimiter fences in a LaTeX formula.

Why this exists
---------------
marker's OCR frequently misreads a fence's OPENING delimiter while reading the
CLOSING one correctly, producing a *mismatched* pair such as::

    \left[ a_m + a_m^\dagger \right)      # open bracket, close paren

A mismatched fence is never valid mathematics -- it is always an extraction
typo. When the task asks for a *fixed* version of a problematic formula, the
correct repair is to turn the mismatched pair into a MATCHED pair. Which
delimiter to keep is exactly the point agents flip-flop on (some collapse the
example above to ``\left[...\right]``, some to ``\left(...\right)``), so this
helper makes the choice deterministic.

Rule
----
For every ``\left<D1> ... \right<D2>`` pair whose two delimiters do not match,
adopt the CLOSING delimiter and rewrite the OPENING one to its partner:

    \left[ ... \right)  ->  \left( ... \right)
    \left( ... \right]  ->  \left[ ... \right]

Rationale: (1) marker misreads OPENING delimiters far more often than closing
ones, so the closing delimiter is the more trustworthy signal; (2) it avoids
redundant same-type nesting like ``[[...]]`` -- mathematical convention
alternates delimiter types when nesting (e.g. ``[ ( ... ) ]``).

Already-matched fences and plain (non-``\left/\right``) brackets are left
untouched, so running this on a correct formula is a no-op. Use it ONLY to
generate the *fixed* line; keep the mismatched form verbatim in the *original*
line so it still reproduces the PDF's display.

Usage
-----
    python scripts/fix_delimiters.py '<formula>'     # prints repaired formula
    echo '<formula>' | python scripts/fix_delimiters.py
    from scripts.fix_delimiters import fix_delimiters; fix_delimiters(s) -> str
"""
from __future__ import annotations

import re
import sys

# Closing delimiter token -> its matching opening token.
_CLOSE_TO_OPEN = {
    ")": "(",
    "]": "[",
    r"\}": r"\{",
    r"\rangle": r"\langle",
    r"\rceil": r"\lceil",
    r"\rfloor": r"\lfloor",
    # symmetric / neutral delimiters map to themselves
    r"\|": r"\|",
    "|": "|",
    ".": ".",
}
# Opening delimiter token -> its matching closing token (inverse of the above).
_OPEN_TO_CLOSE = {v: k for k, v in _CLOSE_TO_OPEN.items()}

# All delimiter tokens that may follow \left or \right, longest first so the
# regex prefers e.g. \rangle over a bare backslash form.
_DELIMS = [
    r"\langle", r"\rangle", r"\lceil", r"\rceil", r"\lfloor", r"\rfloor",
    r"\{", r"\}", r"\|", r"\.", r"\(", r"\)", r"\[", r"\]",
    "(", ")", "[", "]", "|", ".", "<", ">", "/",
]
_DELIM_ALT = "|".join(re.escape(d) for d in _DELIMS)
_TOKEN_RE = re.compile(r"\\(left|right)\s*(" + _DELIM_ALT + r")")


def _norm(tok: str) -> str:
    """Normalise a delimiter token (drop an escaping backslash for . { } etc.)."""
    if tok in (r"\.", r"\(", r"\)", r"\[", r"\]"):
        return tok[1:]
    return tok


def _matches(open_tok: str, close_tok: str) -> bool:
    return _OPEN_TO_CLOSE.get(open_tok) == close_tok


def fix_delimiters(formula: str) -> str:
    r"""Return ``formula`` with every mismatched ``\left..\right`` pair repaired."""
    tokens = list(_TOKEN_RE.finditer(formula))
    if not tokens:
        return formula

    # Pair \left with \right using a stack, then decide replacements.
    stack: list[int] = []          # indices into `tokens` of open \left's
    replacements: dict[int, str] = {}  # token index -> replacement delimiter token
    for idx, m in enumerate(tokens):
        kind = m.group(1)
        if kind == "left":
            stack.append(idx)
        else:  # right
            if not stack:
                continue
            open_idx = stack.pop()
            open_tok = _norm(tokens[open_idx].group(2))
            close_tok = _norm(m.group(2))
            if not _matches(open_tok, close_tok):
                # Adopt the closing delimiter: rewrite the opener to its partner.
                fixed_open = _CLOSE_TO_OPEN.get(close_tok)
                if fixed_open is not None:
                    replacements[open_idx] = fixed_open

    if not replacements:
        return formula

    # Rebuild the string, substituting only the opening delimiters we fixed.
    out = []
    last = 0
    for idx, m in enumerate(tokens):
        if idx in replacements:
            out.append(formula[last:m.start()])
            out.append(r"\left" + replacements[idx])
            last = m.end()
    out.append(formula[last:])
    return "".join(out)


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        text = " ".join(argv[1:])
    else:
        text = sys.stdin.read()
    # Process line by line so a multi-formula file is handled cleanly.
    for line in text.splitlines() or [text]:
        sys.stdout.write(fix_delimiters(line) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
