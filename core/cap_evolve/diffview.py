"""Terminal diffs between two candidate snapshots. Stdlib only.

Every candidate in a run is a directory snapshot under ``<run>/candidates/<id>/`` (see
:meth:`cap_evolve.rundir.RunDir.snapshot`), so "what did this iteration actually change?"
is a directory-vs-directory diff. This module answers that question in the terminal:

``read_tree(dir) -> {relpath: text}``
    The comparable files of one snapshot (text only; prompt/memory scaffolding skipped).

``diffstat(a, b) -> [(path, added, removed)]``
    Per-file counts, plus :func:`render_stat` to draw them with a ``+++---`` bar.

``render(a, b, ...) -> list[str]``
    The full diff. Unified with ``+``/``-`` gutters and ``@@`` hunk headers below
    ``SIDE_BY_SIDE_COLS`` columns, side-by-side above it, with word-level highlighting
    inside a changed line pair. Truncates to ``max_lines`` and says how many lines it
    dropped — an honest "… N more lines", never a silent cut.

Everything is a pure function of its inputs and a width, so the whole view is testable
without a terminal or a run.

**Diff text is model-authored.** An optimizer agent writes the candidate files, so every
line that can reach the terminal goes through :func:`cap_evolve.eventstream.sanitize`
before any styling is added — the same defense the event stream uses.
"""

from __future__ import annotations

import difflib
import json
import re
from pathlib import Path

from . import eventstream, types

__all__ = ["read_tree", "diffstat", "render", "render_stat", "render_files",
           "parent_of", "resolve_pair", "SKIP_FILES", "SIDE_BY_SIDE_COLS"]

#: Optimizer bookkeeping that lives beside the capability in a snapshot but is not a
#: capability edit. Showing it buries the one line that actually changed.
SKIP_FILES = types.NON_CAPABILITY_FILES

#: Read-context directories (never the edit surface).
SKIP_DIRS = ("trajectories", "guidance", *sorted(types.NON_CAPABILITY_DIRS))

#: Side-by-side needs two readable columns; below this we go unified.
SIDE_BY_SIDE_COLS = 120

#: Refuse to read a file bigger than this into a diff (a snapshot can contain a dump).
MAX_BYTES = 512_000

_WORD = re.compile(r"(\w+|\s+|.)")


class _Pal:
    """Diff styles, gated on ``color`` once so a no-color render is provably ANSI-free."""

    __slots__ = ("add", "rem", "hunk", "path", "grey", "bold", "add_hi", "rem_hi", "off")

    def __init__(self, color: bool):
        self.off = "\x1b[0m" if color else ""
        self.add = "\x1b[32m" if color else ""
        self.rem = "\x1b[31m" if color else ""
        self.hunk = "\x1b[36m" if color else ""
        self.path = "\x1b[1m" if color else ""
        self.grey = "\x1b[90m" if color else ""
        self.bold = "\x1b[1m" if color else ""
        # Intra-line emphasis: bright + underline on the words that actually differ.
        self.add_hi = "\x1b[1;4;32m" if color else ""
        self.rem_hi = "\x1b[1;4;31m" if color else ""

    def s(self, text: str, code: str) -> str:
        return f"{code}{text}{self.off}" if code else text


# ---- reading snapshots ------------------------------------------------------

def read_tree(d) -> dict[str, str]:
    """``{relpath: text}`` for one candidate snapshot. Never raises.

    Binary, oversized and unreadable files are skipped rather than crashing the view;
    a missing directory yields ``{}`` so a caller can report "not snapshotted".
    """
    d = Path(d)
    out: dict[str, str] = {}
    if not d.is_dir():
        return out
    for f in sorted(d.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(d).as_posix()
        if rel in SKIP_FILES or rel.split("/", 1)[0] in SKIP_DIRS:
            continue
        try:
            if f.stat().st_size > MAX_BYTES:
                continue
            out[rel] = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
    return out


def parent_of(run_root, candidate: str) -> str | None:
    """The parent candidate id from the run's ``events.jsonl``, or ``None``.

    Read straight from the log rather than through ``dashboard.reduce_run`` so
    ``cap-evolve diff`` works on a half-written run dir with no ``state.json``.
    """
    path = Path(run_root) / "events.jsonl"
    if not path.exists():
        return None
    parent = None
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line[0] != "{":
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(ev, dict):
                continue
            cid = ev.get("candidate") or ev.get("candidate_id") or ev.get("id")
            if cid != candidate:
                continue
            p = ev.get("parent_id") or ev.get("parent")
            if p:
                parent = str(p)
    except OSError:
        return None
    return parent


def best_id(run_root) -> str | None:
    """The winning candidate id: ``final.json`` first, then ``state.json``."""
    for name, key in (("final.json", "best_id"), ("state.json", "best_id")):
        p = Path(run_root) / name
        if not p.exists():
            continue
        try:
            v = (json.loads(p.read_text(encoding="utf-8")) or {}).get(key)
        except (OSError, json.JSONDecodeError):
            continue
        if v:
            return str(v)
    return None


def resolve_pair(run_root, candidate: str | None, *, vs: str | None = None,
                 best: bool = False) -> tuple[str, str, str]:
    """``(a_id, b_id, how)`` — which two snapshots to compare, and why.

    ``--best`` is seed → the winning candidate. Otherwise ``candidate`` against
    ``--vs``, defaulting to its parent (so the default answers "what did THIS
    iteration change?"). ``how`` is a human sentence for the header.
    """
    if best:
        b = best_id(run_root)
        if not b:
            raise LookupError("no best candidate recorded yet (no final.json / state.json)")
        return "seed", b, "seed → best"
    if not candidate:
        raise LookupError("name a candidate, or pass --best")
    if vs:
        return vs, candidate, f"{vs} → {candidate}"
    p = parent_of(run_root, candidate)
    if not p:
        return "seed", candidate, f"seed → {candidate} (no parent recorded)"
    return p, candidate, f"parent {p} → {candidate}"


# ---- stats -----------------------------------------------------------------

def diffstat(a: dict[str, str], b: dict[str, str]) -> list[tuple[str, int, int]]:
    """``[(path, added, removed)]`` for every file that differs, path-sorted."""
    out = []
    for path in sorted(set(a) | set(b)):
        old, new = a.get(path, "").splitlines(), b.get(path, "").splitlines()
        if old == new:
            continue
        added = removed = 0
        for line in difflib.unified_diff(old, new, lineterm="", n=0):
            if line.startswith("+") and not line.startswith("+++"):
                added += 1
            elif line.startswith("-") and not line.startswith("---"):
                removed += 1
        out.append((path, added, removed))
    return out


def render_stat(a: dict[str, str], b: dict[str, str], *, width: int = 100,
                color: bool = False) -> list[str]:
    """``git diff --stat``-shaped summary: per-file counts plus a ``+++---`` bar."""
    p = _Pal(color)
    stats = diffstat(a, b)
    if not stats:
        return [p.s("  no textual difference between these two snapshots", p.grey)]
    name_w = min(max(len(s[0]) for s in stats), max(12, width - 34))
    peak = max((s[1] + s[2]) for s in stats) or 1
    bar_w = max(4, min(30, width - name_w - 18))
    out = []
    for path, added, removed in stats:
        total = added + removed
        n = max(1, round(total / peak * bar_w))
        plus = max(1, round(n * added / total)) if added else 0
        minus = max(0, n - plus)
        out.append("  " + _clip(path, name_w).ljust(name_w) + " "
                   + f"{total:>5} ".rjust(6)
                   + p.s("+" * plus, p.add) + p.s("-" * minus, p.rem))
    files = len(stats)
    tot_a = sum(s[1] for s in stats)
    tot_r = sum(s[2] for s in stats)
    out.append("  " + p.s(_clip(f"{files} file{'s' if files != 1 else ''} changed, "
                                f"{tot_a} insertion(s), {tot_r} deletion(s)",
                                max(1, width - 2)), p.grey))
    return out


def render_files(a: dict[str, str], b: dict[str, str], *, color: bool = False) -> list[str]:
    """One line per changed path with its change kind — the ``--files`` view."""
    p = _Pal(color)
    out = []
    for path, added, removed in diffstat(a, b):
        if path not in a:
            kind, code = "added  ", p.add
        elif path not in b:
            kind, code = "deleted", p.rem
        else:
            kind, code = "changed", p.hunk
        out.append(f"  {p.s(kind, code)}  {_san(path)}  {p.s(f'+{added} -{removed}', p.grey)}")
    return out or [p.s("  no textual difference between these two snapshots", p.grey)]


# ---- the diff itself -------------------------------------------------------

def _san(text: str) -> str:
    """Sanitize one line of model-authored content before it can reach the terminal."""
    return eventstream.sanitize(str(text)).expandtabs(4)


def _clip(text: str, width: int) -> str:
    if width <= 1 or len(text) <= width:
        return text
    return text[: max(1, width - 1)] + "…"


def _word_spans(old: str, new: str) -> tuple[list[tuple[str, bool]], list[tuple[str, bool]]]:
    """Split a changed line pair into ``(text, is_changed)`` runs, word-granular.

    Cheap and bounded: skipped entirely by the caller for very long lines, because
    ``SequenceMatcher`` on a minified blob is where a diff viewer goes to die.
    """
    ow = _WORD.findall(old)
    nw = _WORD.findall(new)
    sm = difflib.SequenceMatcher(a=ow, b=nw, autojunk=False)
    left: list[tuple[str, bool]] = []
    right: list[tuple[str, bool]] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        same = tag == "equal"
        if i1 != i2:
            left.append(("".join(ow[i1:i2]), not same))
        if j1 != j2:
            right.append(("".join(nw[j1:j2]), not same))
    return left, right


_MAX_WORD_DIFF = 400  # chars; beyond this intra-line highlighting is skipped


def _paint_runs(runs, base: str, hi: str, p: _Pal, width: int) -> str:
    """Draw ``(text, changed)`` runs cropped to ``width`` VISIBLE columns.

    Cropping happens on the plain text before styling, so a truncated cell can never
    end inside an escape sequence.
    """
    out, used = [], 0
    for text, changed in runs:
        if used >= width:
            break
        t = text[: width - used]
        used += len(t)
        out.append(p.s(t, hi if changed else base))
    if used < width:
        out.append(" " * (width - used))
    return "".join(out)


def _pairs(old: list[str], new: list[str], context: int):
    """Yield ``("hunk", header)`` / ``("ctx"|"add"|"del"|"mod", ...)`` rows.

    ``"mod"`` carries a ``(-, +)`` line pair so the renderer can highlight the words
    that actually changed instead of two whole red/green lines.
    """
    sm = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    for group in sm.get_grouped_opcodes(context):
        i1, i2 = group[0][1], group[-1][2]
        j1, j2 = group[0][3], group[-1][4]
        yield ("hunk", f"@@ -{i1 + 1},{i2 - i1} +{j1 + 1},{j2 - j1} @@", None)
        for tag, a1, a2, b1, b2 in group:
            if tag == "equal":
                for line in old[a1:a2]:
                    yield ("ctx", line, line)
            elif tag == "replace":
                width = max(a2 - a1, b2 - b1)
                for k in range(width):
                    o = old[a1 + k] if a1 + k < a2 else None
                    n = new[b1 + k] if b1 + k < b2 else None
                    if o is not None and n is not None:
                        yield ("mod", o, n)
                    elif o is not None:
                        yield ("del", o, None)
                    else:
                        yield ("add", None, n)
            elif tag == "delete":
                for line in old[a1:a2]:
                    yield ("del", line, None)
            else:
                for line in new[b1:b2]:
                    yield ("add", None, line)


def render(a: dict[str, str], b: dict[str, str], *, width: int = 100, color: bool = False,
           context: int = 3, side_by_side: bool | None = None,
           max_lines: int = 400, labels: tuple[str, str] | None = None) -> list[str]:
    """The diff of snapshot ``a`` → snapshot ``b`` as terminal lines.

    ``side_by_side=None`` decides on ``width`` (:data:`SIDE_BY_SIDE_COLS`).
    ``labels`` names the two columns in side-by-side mode (which side is which is not
    otherwise guessable from two columns of prose).
    Truncation is explicit: the last line says how many lines were not shown.
    """
    p = _Pal(color)
    try:
        width = max(24, int(width))
    except (TypeError, ValueError):
        width = 80
    if side_by_side is None:
        side_by_side = width >= SIDE_BY_SIDE_COLS
    stats = diffstat(a, b)
    if not stats:
        return [p.s(_clip("  no textual difference between these two snapshots",
                          width), p.grey)]

    out: list[str] = []
    dropped = 0
    for path, added, removed in stats:
        counts = f"+{added} -{removed}"
        head = (f"  {p.s(_clip(_san(path), max(1, width - 4 - len(counts))), p.path)}  "
                f"{p.s(f'+{added}', p.add)} {p.s(f'-{removed}', p.rem)}")
        if len(out) >= max_lines:
            dropped += 1 + _count_rows(a.get(path, ""), b.get(path, ""), context)
            continue
        out.append(head)
        if side_by_side and labels:
            col = _sbs_col(width)
            out.append("    " + p.s(_clip(_san(labels[0]), col).ljust(col), p.grey)
                       + " " + p.s("│", p.grey) + "   "
                       + p.s(_clip(_san(labels[1]), col), p.grey))
        rows = list(_pairs(a.get(path, "").splitlines(), b.get(path, "").splitlines(), context))
        for kind, old, new in rows:
            if len(out) >= max_lines:
                dropped += 1
                continue
            out.extend(_row(kind, old, new, p, width, side_by_side))
        out.append("")
    while out and not out[-1]:
        out.pop()
    if dropped:
        out.append(p.s(_clip(f"  … {dropped} more line(s) not shown "
                             f"(raise --max-lines, or narrow with a path)",
                             max(1, width)), p.grey))
    return out


def _count_rows(old_text: str, new_text: str, context: int) -> int:
    return sum(1 for _ in _pairs(old_text.splitlines(), new_text.splitlines(), context))


def _sbs_col(width: int) -> int:
    """Visible width of ONE side-by-side column.

    Layout is ``"  " + lg + " " + col + " │ " + rg + " " + col`` — two spaces of
    margin, a gutter per column, and the divider: 9 fixed cells. Both the label
    header and every row derive their column from here so they can never drift.
    """
    return max(4, (width - 9) // 2)


def _row(kind: str, old, new, p: _Pal, width: int, side_by_side: bool) -> list[str]:
    """One diff row → one rendered line (unified) or one two-column line."""
    if kind == "hunk":
        return [p.s("  " + _clip(_san(old), width - 2), p.hunk)]
    if not side_by_side:
        if kind == "mod":
            left, right = ((_word_spans(old, new)) if len(old) + len(new) <= _MAX_WORD_DIFF
                           else ([(old, True)], [(new, True)]))
            body = width - 4
            return ["  " + p.s("-", p.rem) + " "
                    + _paint_runs(_runs_san(left), p.rem, p.rem_hi, p, body).rstrip(),
                    "  " + p.s("+", p.add) + " "
                    + _paint_runs(_runs_san(right), p.add, p.add_hi, p, body).rstrip()]
        gutter, style, text = {
            "add": ("+", p.add, new), "del": ("-", p.rem, old), "ctx": (" ", "", old),
        }[kind]
        return ["  " + p.s(gutter, style) + " "
                + p.s(_clip(_san(text), width - 4), style).rstrip()]

    # side-by-side: lg | old | new, with a gutter PER column. A "+" belongs to the
    # right column only: marking a right-only line with "+" on the left reads as if
    # the old side gained it, which is the opposite of what happened.
    col = _sbs_col(width)
    lg = p.s("-", p.rem) if kind in ("del", "mod") else " "
    rg = p.s("+", p.add) if kind in ("add", "mod") else " "
    if kind == "mod" and len(old) + len(new) <= _MAX_WORD_DIFF:
        lr, rr = _word_spans(old, new)
        left = _paint_runs(_runs_san(lr), p.rem, p.rem_hi, p, col)
        right = _paint_runs(_runs_san(rr), p.add, p.add_hi, p, col)
        return [f"  {lg} {left} {p.s('│', p.grey)} {rg} {right}".rstrip()]
    lo = "" if kind == "add" else _clip(_san(old), col)
    ne = "" if kind == "del" else _clip(_san(new), col)
    lstyle = p.rem if kind == "del" else ""
    rstyle = p.add if kind == "add" else ""
    return [f"  {lg} {p.s(lo.ljust(col), lstyle)} "
            f"{p.s('│', p.grey)} {rg} {p.s(ne.ljust(col), rstyle)}".rstrip()]


def _runs_san(runs) -> list[tuple[str, bool]]:
    return [(_san(t), ch) for t, ch in runs]


def summary_line(a: dict[str, str], b: dict[str, str]) -> str:
    """One plain line for a live panel: ``3 files  +12 -4``, or a stated absence."""
    stats = diffstat(a, b)
    if not stats:
        return "no textual change"
    return (f"{len(stats)} file{'s' if len(stats) != 1 else ''}  "
            f"+{sum(s[1] for s in stats)} -{sum(s[2] for s in stats)}")


if __name__ == "__main__":  # self-check
    A = {"p.txt": "hello world\nkeep\n"}
    B = {"p.txt": "hello brave world\nkeep\n", "n.txt": "new\n"}
    assert diffstat(A, B) == [("n.txt", 1, 0), ("p.txt", 1, 1)]
    for w in (24, 80, 100, 200):
        for col in (False, True):
            for lines in render(A, B, width=w, color=col):
                assert len(lines) >= 0
    plain = "\n".join(render(A, B, width=100, color=False))
    assert "\x1b" not in plain and "brave" in plain
    hostile = {"x": "\x1b]0;pwned\x07\x1b[2J boom\n"}
    assert "\x1b" not in "\n".join(render({}, hostile, width=80, color=False))
    assert summary_line(A, A) == "no textual change"
    print("diffview self-check ok")
