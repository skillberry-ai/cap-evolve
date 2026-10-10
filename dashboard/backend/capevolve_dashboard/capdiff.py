"""Capability-only diffs for ``GET /api/runs/{id}/capdiff`` (issue #702).

Only capability files are compared (``diffview.read_tree`` already drops memory/journal/
diagnosis/work bookkeeping; a node's ``capability_files`` narrows it further when recorded).
Rows use the engine's ``{"t": add|del|ctx|hunk, "l": text}`` shape; merge hunks also carry
``c`` = ``inherited:<parent>[,<parent>]`` | ``inherited:both`` | ``reverted`` | ``new``.
"""
from __future__ import annotations

import difflib
import re
from pathlib import Path

from . import _bootstrap  # noqa: F401
from cap_evolve import RunDir, diffview, lineage
from cap_evolve.candidate_graph import CandidateGraph

_TAG = re.compile(r"[\w.\-]+")
_BASES = ("parent", "latest_base", "original", "selected", "ancestry")


MAX_CHARS = 256 * 1024  # per-file cap on diff row text; beyond it rows are cut and ``truncated`` set


class Unavailable(Exception):
    """A candidate snapshot that was never saved (synthetic/pruned): reported, not an error."""


class CapDiffError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


def _tag(t: str) -> str:
    if not _TAG.fullmatch(t or "") or t in (".", ".."):
        raise CapDiffError(400, f"bad candidate tag {t!r}")
    return t


class _Ctx:
    def __init__(self, run_path: Path):
        self.rd = RunDir.open(run_path)
        self.g = CandidateGraph.load(self.rd)
        self._trees: dict[str, dict[str, str]] = {}

    def parents(self, tag: str) -> list[str]:
        ps = self.g.parents_of(tag)
        if not ps and tag != "seed":
            p = diffview.parent_of(self.rd.root, tag)
            ps = [p] if p and p != tag else ["seed"]
        return ps

    def tree_or_empty(self, tag: str) -> dict[str, str]:
        try:
            return self.tree(tag)
        except Unavailable:
            return {}

    def tree(self, tag: str) -> dict[str, str]:
        if tag not in self._trees:
            d = self.rd.root / "candidates" / _tag(tag)
            if not d.is_dir():
                raise Unavailable(f"no snapshot for candidate {tag!r}")
            t = diffview.read_tree(d)
            only = (self.g.node(tag) or {}).get("capability_files")
            self._trees[tag] = {k: v for k, v in t.items() if k in only} if only else t
        return self._trees[tag]

    def merge_base(self, parents: list[str], node: dict | None) -> str:
        if node and node.get("merge_base"):
            return node["merge_base"]
        o = parents[0]
        for p in parents[1:]:
            o = lineage.merge_base(self.g, o, p)
        return o


def _lines(s: str) -> list[str]:
    return s.splitlines()


def _hunks(old: list[str], new: list[str]):
    """Non-equal opcodes ``(i1, i2, j1, j2)``; context 0 so hunks are the minimal edits."""
    sm = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    return [(i1, i2, j1, j2) for t, i1, i2, j1, j2 in sm.get_opcodes() if t != "equal"]


def _key(old, new, h):
    i1, i2, j1, j2 = h
    return (i1, tuple(old[i1:i2]), tuple(new[j1:j2]))


def _rows(old: list[str], new: list[str], classes: dict | None = None, context: int = 2) -> list[dict]:
    """Unified rows old -> new; ``classes`` maps an (i1, old, new) hunk key to a merge class."""
    rows: list[dict] = []
    sm = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    for group in sm.get_grouped_opcodes(context):
        rows.append({"t": "hunk", "l": f"@@ -{group[0][1] + 1} +{group[0][3] + 1} @@"})
        for t, i1, i2, j1, j2 in group:
            if t == "equal":
                rows += [{"t": "ctx", "l": x} for x in old[i1:i2]]
                continue
            c = (classes or {}).get((i1, tuple(old[i1:i2]), tuple(new[j1:j2])))
            extra = {"c": c} if c else {}
            rows += [{"t": "del", "l": x, **extra} for x in old[i1:i2]]
            rows += [{"t": "add", "l": x, **extra} for x in new[j1:j2]]
    return rows


def _file_entry(path, rows):
    size, cut = 0, None
    for i, r in enumerate(rows):
        size += len(r["l"])
        if size > MAX_CHARS:
            cut = i
            break
    if cut is not None:
        rows = rows[:cut]
    return {"path": path, "truncated": cut is not None, "added": sum(r["t"] == "add" for r in rows),
            "removed": sum(r["t"] == "del" for r in rows), "rows": rows}


def diff_trees(a: dict[str, str], b: dict[str, str]) -> list[dict]:
    out = []
    for path in sorted(set(a) | set(b)):
        if a.get(path) != b.get(path):
            out.append(_file_entry(path, _rows(_lines(a.get(path, "")), _lines(b.get(path, "")))))
    return out


def classify_merge(base: dict[str, str], parents: dict[str, dict[str, str]],
                   result: dict[str, str]) -> list[dict]:
    """3-way classification of a merge result against its merge-base ``base``.

    A result hunk (base -> result) is ``inherited:<p>`` when a parent made the identical
    change at the same base location, ``new`` when no parent did (merge-specific). A parent
    hunk the result does not carry and whose base lines the result left untouched is
    ``reverted`` (shown as the parent's added lines being dropped)."""
    names, out = list(parents), []
    for path in sorted(set(base) | set(result) | {p for t in parents.values() for p in t}):
        o, c = _lines(base.get(path, "")), _lines(result.get(path, ""))
        per_parent = {p: {_key(o, _lines(t.get(path, "")), h): h
                          for h in _hunks(o, _lines(t.get(path, "")))} for p, t in parents.items()}
        c_hunks = _hunks(o, c)
        classes = {}
        for h in c_hunks:
            k = _key(o, c, h)
            who = [p for p in names if k in per_parent[p]]
            # N parents: one -> inherited:<p>; all of exactly 2 -> inherited:both;
            # two or more otherwise -> inherited:multiple (rows carry the list in ``by``)
            classes[k] = ("new" if not who else
                          "inherited:" + who[0] if len(who) == 1 else
                          "inherited:both" if len(who) == len(names) == 2 else
                          "inherited:multiple")
        rows = _rows(o, c, classes) if c_hunks else []
        for p in names:
            pl = _lines(parents[p].get(path, ""))
            for k, (i1, i2, j1, j2) in per_parent[p].items():
                if k in classes or any(not (i2 < ci1 or ci2 < i1) for ci1, ci2, _, _ in c_hunks):
                    continue
                rows.append({"t": "hunk", "l": f"@@ reverted parent change from {p} @@"})
                rows += [{"t": "ctx", "l": x, "c": "reverted"} for x in o[i1:i2]]
                rows += [{"t": "del", "l": x, "c": "reverted"} for x in pl[j1:j2]]
        if rows:
            out.append(_file_entry(path, rows))
    return out


def edge_diff(ctx: _Ctx, tag: str, parent: str | None = None) -> dict:
    """Diff of ``tag`` against its parent; a multi-parent node gets merge classification."""
    ps = ctx.parents(tag)
    if len(ps) > 1 and parent is None:
        base = ctx.merge_base(ps, ctx.g.node(tag))
        return {"base": base, "parents": ps, "merge": True,
                "files": classify_merge(ctx.tree(base), {p: ctx.tree(p) for p in ps}, ctx.tree(tag))}
    p = parent or ps[0]
    return {"base": p, "parents": [p], "merge": False, "files": diff_trees(ctx.tree(p), ctx.tree(tag))}


def _chain(ctx: _Ctx, tag: str) -> list[str]:
    """seed -> ... -> tag along first parents."""
    chain, seen = [tag], {tag}
    while chain[-1] != "seed":
        p = ctx.parents(chain[-1])[0] if ctx.parents(chain[-1]) else "seed"
        if p in seen:
            break
        chain.append(p)
        seen.add(p)
    return chain[::-1]


def blame(ctx: _Ctx, target: str) -> dict[str, list[dict]]:
    """``{path: [{start, end, by}]}`` -- 1-based line runs of ``target`` and the candidate
    that introduced them. Follows ALL parents: a line of a node that aligns (difflib) with a
    line of a parent keeps that parent's blame; lines aligned with several parents are
    credited to the FIRST parent in the node's ``parents`` order (deterministic tie-break,
    also for criss-cross graphs); lines aligned with none are the node's own (for a merge:
    merge-specific). A node with no saved snapshot is treated as empty, so its lines are
    credited to its first descendant that has one."""
    memo: dict[str, dict[str, list[str]]] = {}

    def own(tag, stack=()):
        if tag in memo:
            return memo[tag]
        try:
            cur = ctx.tree(tag)
        except Unavailable:
            cur = {}
        ps = [] if tag == "seed" or tag in stack else ctx.parents(tag)
        pown = [own(p, stack + (tag,)) for p in ps]
        out = {}
        for path, text in cur.items():
            new_l = _lines(text)
            o = ["seed" if tag == "seed" else tag] * len(new_l)
            taken = [False] * len(new_l)
            for p, po in zip(ps, pown):
                old_l = _lines(ctx.tree_or_empty(p).get(path, ""))
                for t, i1, i2, j1, j2 in difflib.SequenceMatcher(a=old_l, b=new_l, autojunk=False).get_opcodes():
                    if t == "equal":
                        for k in range(j2 - j1):
                            if not taken[j1 + k] and i1 + k < len(po.get(path, [])):
                                o[j1 + k], taken[j1 + k] = po[path][i1 + k], True
            out[path] = o
        memo[tag] = out
        return out

    out = {}
    for path, o in own(target).items():
        runs: list[dict] = []
        for i, by in enumerate(o, 1):
            if runs and runs[-1]["by"] == by:
                runs[-1]["end"] = i
            else:
                runs.append({"start": i, "end": i, "by": by})
        out[path] = runs
    return out


def capdiff(run_path: Path, target: str, base: str = "parent", selected: str | None = None) -> dict:
    """``base=selected`` compares against the ``selected`` tag, default the run's current best."""
    res = {"target": _tag(target), "mode": base if base in _BASES else "tag"}
    try:
        res.update(_capdiff(run_path, res["target"], base, selected))
    except Unavailable as e:
        res.update(unavailable=True, reason=str(e), files=[])
    res["truncated"] = any(f.get("truncated") for f in res.get("files", []) +
                           [f for e in res.get("edges", []) for f in e["files"]])
    return res


def _capdiff(run_path: Path, target: str, base: str, selected: str | None) -> dict:
    ctx = _Ctx(run_path)
    ctx.tree(target)
    node = ctx.g.node(target) or {}
    res: dict = {}
    if base == "ancestry":
        chain = _chain(ctx, target)
        res["edges"] = [{"from": a, "to": b, **edge_diff(ctx, b, parent=a if len(ctx.parents(b)) < 2 else None)}
                        for a, b in zip(chain, chain[1:])]
        res["blame"] = blame(ctx, target)
        return res
    if base == "parent":
        return edge_diff(ctx, target)
    if base == "latest_base":
        b = node.get("base_for_eval") or (ctx.parents(target) or ["seed"])[0]
    elif base == "original":
        b = "seed"
    elif base == "selected":
        b = _tag(selected) if selected else diffview.best_id(ctx.rd.root)
        if not b:
            raise Unavailable("no selected candidate recorded yet")
    else:
        b = _tag(base)
    return {"base": b, "parents": [b], "merge": False, "files": diff_trees(ctx.tree(b), ctx.tree(target))}
