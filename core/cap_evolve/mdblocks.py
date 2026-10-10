"""mdblocks — heading-path block split + 3-way verdict for prose files (#709).

`merge_search.is_mergeable` treated every non-.py file as ONE module, so two siblings that
edited different sections of the same policy.md reported a false collision. This is the
prose analogue of `funcmerge.blocks`: a block is a heading section (id = heading path), with a
paragraph fallback for headingless / oversized sections. Pure, stdlib only.
"""

from __future__ import annotations

import re

_HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*?)[ \t#]*$")
_FENCE = re.compile(r"^ {0,3}(```|~~~)")


def _sections(text: str) -> list[tuple[str, list[str]]]:
    """[(id, lines)] covering `text` exactly, in order. Preamble (before first heading) is id ''."""
    out: list[tuple[str, list[str]]] = []
    stack: list[tuple[int, str]] = []
    seen: dict[str, int] = {}
    cur: list[str] = []
    cur_id, in_fence = "", False
    for ln in text.splitlines(keepends=True):
        if _FENCE.match(ln):
            in_fence = not in_fence
        m = None if in_fence else _HEADING.match(ln.rstrip("\r\n"))
        if m:
            if cur:
                out.append((cur_id, cur))
            level = len(m.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, m.group(2)))
            cur_id = "/".join(t for _, t in stack)
            seen[cur_id] = seen.get(cur_id, 0) + 1
            if seen[cur_id] > 1:
                cur_id += f"#{seen[cur_id]}"
            cur = [ln]
        else:
            cur.append(ln)
    if cur:
        out.append((cur_id, cur))
    return out


def _paragraphs(sec_id: str, lines: list[str]) -> list[tuple[str, list[str]]]:
    """Split one section on blank lines. id = section + first normalized line + occurrence, so
    editing one paragraph does not rename its neighbours (unlike a positional index)."""
    paras: list[list[str]] = []
    for i, ln in enumerate(lines):
        if i and ln.strip() and not lines[i - 1].strip():
            paras.append([])
        if not paras:
            paras.append([])
        paras[-1].append(ln)
    seen: dict[str, int] = {}
    out = []
    for p in paras:
        key = f"{sec_id}¶{' '.join(p[0].split())}"
        seen[key] = seen.get(key, 0) + 1
        out.append((key if seen[key] == 1 else f"{key}#{seen[key]}", p))
    return out


def split(text: str, max_block_lines: int = 80) -> list[tuple[str, str]]:
    """Ordered [(block_id, text)]; ''.join of the texts == `text`."""
    out: list[tuple[str, str]] = []
    for sec_id, lines in _sections(text):
        for bid, ls in (_paragraphs(sec_id, lines) if len(lines) > max_block_lines else [(sec_id, lines)]):
            out.append((bid, "".join(ls)))
    return out


def three_way(base: str, a: str, b: str, max_block_lines: int = 80) -> dict:
    """Block-level verdict. A block conflicts iff both sides differ from base on it AND from each
    other (a delete counts as a change). `merged_text` is None when there are conflicts."""
    sp = [split(t, max_block_lines) for t in (base, a, b)]
    B, A, C = (dict(s) for s in sp)
    conflicts, identical = [], []
    changed_a, changed_b = [], []
    for bid in dict.fromkeys(i for s in sp for i, _ in s):
        da, db = A.get(bid) != B.get(bid), C.get(bid) != B.get(bid)
        if da:
            changed_a.append(bid)
        if db:
            changed_b.append(bid)
        if da and db:
            (identical if A.get(bid) == C.get(bid) else conflicts).append(bid)
    merged = None if conflicts else _assemble(sp, B, A, C)
    return {"changed_a": changed_a, "changed_b": changed_b, "conflicts": conflicts,
            "identical": identical, "merged_text": merged}


def _assemble(sp, B, A, C) -> str:
    order = [i for i, _ in sp[0]]
    pick = {i: (A.get(i) if A.get(i) != B.get(i) else C.get(i)) if i in B else None for i in order}
    after: dict[str | None, list[str]] = {}
    added: set[str] = set()
    for side in (sp[1], sp[2]):  # new blocks go after their nearest preceding block
        prev = None
        for i, t in side:
            if i not in B and i not in added:
                added.add(i)
                after.setdefault(prev, []).append(i)
                pick[i] = t
            prev = i
    out = [t for i in after.get(None, []) if (t := pick[i])]
    for i in order:
        if pick[i] is not None:
            out.append(pick[i])
        out += [pick[j] for j in after.get(i, [])]
    return "".join(out)
