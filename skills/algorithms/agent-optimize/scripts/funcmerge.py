"""Merge N per-task-optimised copies of one Python file by running 3-way merge PER FUNCTION.

Why this exists. `merge_taskopt.py` runs git's 3-way merge on whole files, and on a real
fan-out that reports conflicts it should not. Measured on the one multi-turn tool-use benchmark: ten
independently-verified optimiser branches, and a whole-file merge kept only four of them. The
"conflicts" were not disagreements. Every optimiser had added

  * one state field to the SAME `__init__`, and
  * one independent guard call to the SAME tool method, right after the same existing check,

so their edits landed on adjacent lines of a shared insertion point. Line-level 3-way merge
cannot tell "two people appended different things here" from "two people rewrote the same
thing", and diff3 conflicts on both. Enabling `--union-on-conflict` to force them through
produced a file that DID NOT PARSE and carried five duplicated `def`s.

The granularity is the bug. Merge each function against its own base instead of merging the
file, and independent additions inside different functions stop interacting at all; only two
branches editing the SAME function can still conflict, which is the question actually worth a
human decision. On the same ten branches this raised retention from 4/10 to the full set.

    python funcmerge.py --base BASE.py --out OUT.py --inputs A.py B.py C.py

Reports, per function: which branches changed it, whether the merge was clean, and any
remaining conflict. A conflict here is a genuine semantic overlap — two branches rewriting one
function — and is left for a decision, never auto-resolved.

Guarantees enforced before writing OUT:
  * the result parses (`ast.parse`), and
  * no `def` name is defined twice,
because the failure this replaces produced a file that violated both.
"""

import argparse
import ast
import difflib
import json
import subprocess
import tempfile
from pathlib import Path


def blocks(src: str) -> tuple[list[str], dict[str, str]]:
    """Split a module into (preamble_lines, {qualified_def_name: source_text}).

    Splitting is done on the AST, not on indentation heuristics, so a `def` inside a
    docstring or a string literal cannot create a phantom block.
    """
    tree = ast.parse(src)
    lines = src.splitlines(keepends=True)
    spans: list[tuple[int, int, str]] = []

    def walk(node, prefix=""):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = f"{prefix}{child.name}"
                start = min([child.lineno] + [d.lineno for d in child.decorator_list]) - 1
                spans.append((start, child.end_lineno, name))
            elif isinstance(child, ast.ClassDef):
                walk(child, prefix=f"{prefix}{child.name}.")
            elif prefix and isinstance(child, (ast.Assign, ast.AnnAssign)):
                # Class-level CONSTANTS are merge units too. Without this they are invisible to
                # a function-granularity merge, which is the exact root cause of the worst bug
                # this tool has produced: a merged function referencing `self.CABIN_LADDER`
                # while the constant stayed behind, crashing at runtime and presenting as a
                # missing write. Carrying them as named blocks makes the whole class of defect
                # impossible rather than merely detected.
                tgts = ([child.target] if isinstance(child, ast.AnnAssign)
                        else list(child.targets))
                names = [t.id for t in tgts if isinstance(t, ast.Name)]
                if len(names) == 1:
                    # a leading `#:` comment block belongs to the constant it documents
                    start = child.lineno - 1
                    while start > 0 and lines[start - 1].lstrip().startswith("#"):
                        start -= 1
                    spans.append((start, child.end_lineno, f"{prefix}{names[0]}"))

    walk(tree)
    spans.sort()
    out: dict[str, str] = {}
    covered = set()
    for start, end, name in spans:
        out[name] = "".join(lines[start:end])
        covered.update(range(start, end))
    pre = [ln for i, ln in enumerate(lines) if i not in covered]
    return pre, out


def pure_insertions(base: str, variant: str) -> list[tuple[int, list[str]]] | None:
    """If `variant` only ADDS lines to `base`, return those insertions; else None.

    This is the test that decides whether a same-function collision is safe to union. Every
    optimiser in a fan-out tends to append one guard call to a shared tool method and one state
    field to a shared `__init__`; those are insertions at a common anchor, and diff3 conflicts on
    them even though the branches do not disagree about anything. But a branch that REWRITES a
    base line is asserting the old line was wrong, and two such assertions cannot both be
    honoured — that one still needs a human decision. So union is offered only for the
    provably-additive case, keyed on position in the BASE so the order of branches cannot change
    the result.
    """
    bl, vl = base.splitlines(keepends=True), variant.splitlines(keepends=True)
    ins: list[tuple[int, list[str]]] = []
    for tag, i1, _i2, j1, j2 in difflib.SequenceMatcher(None, bl, vl).get_opcodes():
        if tag == "equal":
            continue
        if tag == "insert":
            ins.append((i1, vl[j1:j2]))
        else:                      # replace / delete -> a real rewrite
            return None
    return ins


def union_insertions(base: str, variants: list[tuple[str, str]]) -> str | None:
    """Apply every branch's insertions to `base`, deduplicated, anchored to base positions."""
    per = []
    for tag, text in variants:
        got = pure_insertions(base, text)
        if got is None:
            return None
        per.append((tag, got))
    bl = base.splitlines(keepends=True)
    at: dict[int, list[str]] = {}
    # Dedupe WHOLE HUNKS across branches, never individual lines. A branch's own inserted lines
    # are already correct and may legitimately repeat: two dict comprehensions in one `__init__`
    # both contain one shared iteration expression, and de-duplicating by line
    # deleted the second one, truncating the statement into a syntax error that only surfaced as
    # `'{' was never closed`. The only thing worth collapsing is two branches contributing the
    # SAME insertion at the SAME anchor, which is exactly (anchor, hunk).
    seen_hunks: set[tuple[int, tuple[str, ...]]] = set()
    for _tag, ins in per:
        for pos, lines in ins:
            key = (pos, tuple(ln.rstrip("\n") for ln in lines))
            if key in seen_hunks:
                continue
            seen_hunks.add(key)
            at.setdefault(pos, []).extend(lines)
    out: list[str] = []
    for i, ln in enumerate(bl):
        out.extend(at.pop(i, []))
        out.append(ln)
    for pos in sorted(at):
        out.extend(at[pos])
    return "".join(out)


def priority_union(base: str, variants: list[tuple[str, str]], order: list[str],
                   force: bool = False) -> str | None:
    """Resolve a same-function collision as: ONE branch's rewrite + everyone else's insertions.

    The collisions left after `union_insertions` share a shape. Several optimisers each rewrote
    the SAME tool docstring (a real rewrite, so union is not allowed) while ALSO each adding one
    independent guard call to the body (pure insertions, which union is exactly right for).
    Dropping the whole function to a single branch would throw away the other branches' guards —
    on that benchmark that meant losing two branches' fixes to keep a third's
    docstring, which is not a trade anyone would choose deliberately.

    So split the decision. The highest-priority branch (caller-supplied `order`, normally by how
    much val headroom the branch's task holds) wins the rewrite and becomes the trunk. Every
    other branch contributes only its insertions, re-anchored by the CONTENT of the base line
    they followed rather than by line number, since the trunk has shifted those numbers. An
    insertion whose anchor the trunk no longer contains is reported as dropped rather than
    guessed at.
    """
    variants = sorted(variants, key=lambda tv: _trunk_key(base, tv, order))
    trunk_tag, trunk = variants[0]
    bl = base.splitlines(keepends=True)
    tl = trunk.splitlines(keepends=True)
    dropped: list[str] = []
    for tag, text in variants[1:]:
        ins = pure_insertions(base, text)
        if ins is None:
            # A second genuine rewrite of the same function. Without --force-priority this
            # needs a human. WITH it, only this branch's REWRITE is dropped; branches that
            # merely inserted still contribute, because dropping a whole branch for someone
            # else's rewrite is how a merge silently loses a measured fix (here it would have
            # dropped task 42's guard call to resolve a disagreement about a money string).
            if not force:
                return None
            FORCED_REWRITES.append(f"{tag}")
            continue
        for pos, lines in ins:
            anchor = bl[pos - 1] if pos > 0 else None
            if any(ln.strip() and ln.strip() in "".join(tl) for ln in lines):
                continue                     # trunk already carries it
            if anchor is None:
                tl = lines + tl
                continue
            try:
                at = next(i for i in range(len(tl) - 1, -1, -1) if tl[i] == anchor)
            except StopIteration:
                dropped.append(f"{tag}:{lines[0].strip()[:60]}")
                continue
            tl = tl[: at + 1] + lines + tl[at + 1 :]
    out = "".join(tl)
    if dropped:
        out += ""      # reported by caller via PRIORITY_DROPPED
        PRIORITY_DROPPED.extend(dropped)
    return out


def _trunk_key(base: str, tv: tuple[str, str], order: list[str]) -> tuple[int, int]:
    """Sort key choosing which branch becomes the trunk of a contested function.

    Trunk = the branch that CHANGED THIS FUNCTION MOST, measured in lines differing from base;
    the caller's `order` is only a tiebreak. Ordering by the branch's task headroom instead is
    a trap that cost a whole resolution on that benchmark: the branch with the most headroom
    (task 7, a full task-equivalent) turned out to have added exactly ONE line to the contested
    the contested function — its real fix was elsewhere — so making it the trunk
    discarded the branch that had actually rewritten the return value, and kept nothing. What a
    function is worth is not what its author's task is worth.
    """
    tag, text = tv
    bl = base.splitlines()
    changed = sum(1 for ln in difflib.unified_diff(bl, text.splitlines(), lineterm="", n=0)
                  if ln.startswith(("+", "-")) and not ln.startswith(("+++", "---")))
    rank = {t: i for i, t in enumerate(order)}
    return (-changed, rank.get(tag, len(order)))


PRIORITY_DROPPED: list[str] = []
FORCED: list[dict] = []
FORCED_REWRITES: list[str] = []


def merge3(base: str, a: str, b: str) -> tuple[str, bool]:
    """git merge-file on three strings. Returns (text, clean)."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "base").write_text(base)
        (d / "a").write_text(a)
        (d / "b").write_text(b)
        r = subprocess.run(["git", "merge-file", "-p", "--diff3",
                            str(d / "a"), str(d / "base"), str(d / "b")],
                           capture_output=True, text=True)
        return r.stdout, r.returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--inputs", nargs="+", required=True)
    ap.add_argument("--json", dest="json_out", default="")
    ap.add_argument("--priority", nargs="*", default=[],
                    help="branch tags, most important first. When one function was REWRITTEN by "
                         "several branches, the first-listed becomes the trunk and the others "
                         "contribute only their insertions. Order by val headroom, not by name.")
    ap.add_argument("--force-priority", action="store_true",
                    help="for a function TWO branches rewrote, ship the highest-priority "
                         "branch's version whole and REPORT the branches dropped. This is a "
                         "real loss of measured work, so it is reported per function and must "
                         "be re-measured, never assumed harmless.")
    ap.add_argument("--union-pure-insertions", action="store_true",
                    help="resolve a same-function collision by applying every branch's "
                         "insertions when NO branch rewrites a base line (see "
                         "pure_insertions). Anything that rewrites base still conflicts.")
    args = ap.parse_args()

    base_src = Path(args.base).read_text()
    base_pre, base_fns = blocks(base_src)

    variants: dict[str, list[tuple[str, str]]] = {}   # fn -> [(branch, text)]
    pres: list[tuple[str, list[str]]] = []
    order: list[str] = list(base_fns)
    for p in args.inputs:
        tag = Path(p).parent.parent.name if Path(p).parent.name == "tools" else Path(p).stem
        pre, fns = blocks(Path(p).read_text())
        pres.append((tag, pre))
        for name, text in fns.items():
            if name not in base_fns:
                variants.setdefault(name, []).append((tag, text))
                if name not in order:
                    order.append(name)
            elif text != base_fns[name]:
                variants.setdefault(name, []).append((tag, text))

    report: dict[str, dict] = {}
    merged_fns: dict[str, str] = dict(base_fns)
    conflicts: list[str] = []

    for name in order:
        vs = variants.get(name, [])
        if not vs:
            continue
        if name not in base_fns:
            # a NEW function. Two branches adding the same name with different bodies is a
            # real collision; identical bodies (a shared helper) is not.
            uniq = {t for _, t in vs}
            merged_fns[name] = vs[0][1]
            report[name] = {"kind": "added", "branches": [t for t, _ in vs],
                            "identical": len(uniq) == 1}
            if len(uniq) > 1:
                conflicts.append(name)
                report[name]["conflict"] = "same new name, different bodies"
            continue
        cur, clean_all = base_fns[name], True
        for tag, text in vs:
            cur, clean = merge3(base_fns[name], cur, text)
            if not clean:
                clean_all = False
        how = "diff3"
        if not clean_all and args.union_pure_insertions:
            u = union_insertions(base_fns[name], vs)
            if u is not None:
                cur, clean_all, how = u, True, "union-pure-insertions"
            elif args.priority:
                pu = priority_union(base_fns[name], vs, args.priority)
                if pu is not None:
                    cur, clean_all, how = pu, True, "priority-trunk+insertions"
                elif args.force_priority:
                    FORCED_REWRITES.clear()
                    pf = priority_union(base_fns[name], vs, args.priority, force=True)
                    if pf is not None:
                        trunk = min(vs, key=lambda tv: _trunk_key(base_fns[name], tv,
                                                                  args.priority))[0]
                        cur, clean_all, how = pf, True, f"forced-trunk:{trunk}"
                        FORCED.append({"function": name, "trunk": trunk,
                                       "rewrites_dropped": list(FORCED_REWRITES),
                                       "insertions_kept_from": [t for t, _ in vs
                                                                if t != trunk
                                                                and t not in FORCED_REWRITES]})
        merged_fns[name] = cur
        report[name] = {"kind": "modified", "branches": [t for t, _ in vs],
                        "clean": clean_all, "resolved_by": how}
        if not clean_all:
            conflicts.append(name)

    # preamble: base plus any import lines a branch added, in first-seen order
    pre_out = list(base_pre)
    have = set(base_pre)
    for _, pre in pres:
        for ln in pre:
            if ln.startswith(("import ", "from ")) and ln not in have:
                pre_out.insert(len([x for x in pre_out if x.startswith(("import ", "from "))]), ln)
                have.add(ln)

    # Reassemble in the base file's own layout so the diff stays readable: walk the base
    # source and swap each function block for its merged text, appending genuinely new
    # functions after the last function of the class they came from.
    src_lines = base_src.splitlines(keepends=True)
    _, spans = blocks(base_src), None
    tree = ast.parse(base_src)
    placed: list[tuple[int, int, str]] = []

    def walk(node, prefix=""):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                s = min([child.lineno] + [d.lineno for d in child.decorator_list]) - 1
                placed.append((s, child.end_lineno, f"{prefix}{child.name}"))
            elif isinstance(child, ast.ClassDef):
                walk(child, prefix=f"{prefix}{child.name}.")

    walk(tree)
    placed.sort()
    new_names = [n for n in merged_fns if n not in base_fns]
    # A new CONSTANT must land inside the class body, before the first method, or it silently
    # becomes a module-level name and `self.NAME` still fails.
    new_consts = [n for n in new_names if n.rsplit(".", 1)[-1].isupper()]
    new_names = [n for n in new_names if n not in new_consts]
    out_parts: list[str] = []
    cursor = 0
    first_method = placed[0][0] if placed else 0
    for i, (s, e, name) in enumerate(placed):
        if i == 0 and new_consts:
            out_parts.append("".join(src_lines[cursor:s]))
            for cn in new_consts:
                out_parts.append(merged_fns[cn].rstrip("\n") + "\n\n")
            cursor = s
        out_parts.append("".join(src_lines[cursor:s]))
        out_parts.append(merged_fns[name])
        cursor = e
        if i + 1 < len(placed):
            continue
        for n in new_names:                       # append new helpers after the last method
            out_parts.append("\n" + merged_fns[n])
    out_parts.append("".join(src_lines[cursor:]))
    text = "".join(out_parts)

    # add any imports the branches needed
    if pre_out != base_pre:
        added = [ln for ln in pre_out if ln not in base_pre]
        head, sep, rest = text.partition("\n\n")
        text = head + "\n" + "".join(added) + sep + rest

    # POST-MERGE AUDIT: which lines that a branch ADDED did the merge fail to carry?
    #
    # This exists because a forced-trunk resolution can silently re-apply a change the losing
    # branch had already MEASURED AND REVERTED. Observed live: one branch had added a sentence
    # to a `payment_id` Args description and separately recorded, twice, that REMOVING that
    # sentence was harmful. The merge dropped that branch rewrite of the function, which
    # re-performed the exact subtraction its owner had rejected - invisible at whole-file
    # level, and absent from the conflict report, because from the merge point of view nothing
    # conflicted. A gate would then measure the regression without ever naming its cause.
    #
    # The check is cheap and purely structural: any non-trivial line a branch added that is
    # absent from the result is reported. It is advisory, not fatal - some drops are the
    # deliberate outcome of a conflict decision - but it must be READ against the ledger
    # rejected entries before the merged artifact is gated.
    base_lines = set(base_src.splitlines())
    dropped_additions: dict[str, list[str]] = {}
    _fences = ('"""', "'''")
    for p_in in args.inputs:
        tag = (Path(p_in).parent.parent.name if Path(p_in).parent.name == "tools"
               else Path(p_in).stem)
        lost = []
        for ln in Path(p_in).read_text().splitlines():
            t = ln.strip()
            if len(t) < 12 or ln in base_lines or t in _fences:
                continue
            if t not in text:
                lost.append(t[:120])
        if lost:
            dropped_additions[tag] = lost[:12]

    ok, err = True, ""
    try:
        t = ast.parse(text)
        names = [n.name for n in ast.walk(t)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        dups = sorted({n for n in names if names.count(n) > 1})
        if dups:
            ok, err = False, f"duplicate defs: {dups}"
        # Merging FUNCTIONS can drop a class-level CONSTANT that a merged function needs. This
        # is not a style problem, it is a crash: the helper survives, its call site survives,
        # and `self.CABIN_LADDER` raises AttributeError at runtime. The tool layer catches it
        # and hands the agent an error string, so the agent abandons the write and the failure
        # presents as a MISSING WRITE — indistinguishable from a policy failure in the reward,
        # and it silently contaminated four separate measurements before a live tool return
        # exposed it. So resolve it statically: every attribute the result reads off `self`
        # must be defined in the result.
        # Instance attributes are set both plainly (`self.x = 1`) and WITH ANNOTATIONS
        # (`self.x: set[str] = set()`). The latter is ast.AnnAssign, not ast.Assign; collecting
        # only Assign made this check report six valid fields as undefined and hard-fail a good
        # merge. A hard-fail check with false positives is worse than no check at all.
        assigned = set()
        for n in ast.walk(t):
            if isinstance(n, ast.Assign):
                for tgt in n.targets:
                    for x in ast.walk(tgt):
                        if isinstance(x, ast.Attribute):
                            assigned.add(x.attr)
            elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Attribute):
                assigned.add(n.target.attr)
            elif isinstance(n, (ast.AugAssign,)) and isinstance(n.target, ast.Attribute):
                assigned.add(n.target.attr)
        class_attrs, methods = set(), set()
        for n in ast.walk(t):
            if isinstance(n, ast.ClassDef):
                for stmt in n.body:
                    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods.add(stmt.name)
                    for tgt in getattr(stmt, "targets", []) or []:
                        if isinstance(tgt, ast.Name):
                            class_attrs.add(tgt.id)
                    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                        class_attrs.add(stmt.target.id)
        read = {n.attr for n in ast.walk(t)
                if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                and n.value.id == "self" and isinstance(n.ctx, ast.Load)}
        undefined = sorted(read - assigned - class_attrs - methods - set(dir(object)))
        # Only CONSTANT-shaped names hard-fail. The class under merge normally has a base class
        # (so `self.x` may resolve on a base class), and an inherited method called through `self` is not
        # resolvable from this file — hard-failing on those would reject valid merges, which is
        # worse than not checking. Upper-case class constants are the case actually observed
        # crashing (`self.CABIN_LADDER`), and they are not inherited in practice. Everything
        # else is reported for a human to read.
        missing_const = [n for n in undefined if n.isupper()]
        maybe_inherited = [n for n in undefined if not n.isupper()]
        if ok and missing_const:
            ok, err = False, ("undefined on self (a merged function needs a definition the "
                              f"merge did not carry): {missing_const}")
    except SyntaxError as exc:
        ok, err = False, f"SyntaxError: {exc}"

    if ok and not conflicts:
        Path(args.out).write_text(text)
    elif not ok:
        # Write the rejected text next to the target so a syntax failure is INSPECTABLE.
        # A refusal that leaves nothing behind forces the caller to reconstruct the assembly
        # by hand to find out what broke, which is how a tool bug gets worked around instead
        # of fixed.
        Path(str(args.out) + ".rejected").write_text(text)

    result = {
        "base": args.base,
        "inputs": args.inputs,
        "written": bool(ok and not conflicts),
        "out": args.out,
        "parses": ok,
        "error": err,
        "conflicts": conflicts,
        "functions_touched": {k: v for k, v in report.items()},
        "priority_dropped_insertions": PRIORITY_DROPPED,
        "forced_single_branch": FORCED,
        "dropped_additions": dropped_additions,
        "self_attrs_not_defined_here": locals().get("maybe_inherited") or [],
        "dropped_additions_warning": (
            "lines a branch ADDED that the merge did not carry. Check each against the "
            "ledger REJECTED entries: a dropped rewrite can re-apply a subtraction its "
            "owner already measured as harmful." if dropped_additions else ""),
        "next": ("render the LIVE toolset (validate_capability.py) before spending rollouts"
                 if ok and not conflicts else
                 "resolve the listed conflicts by hand — two branches rewrote one function"),
    }
    print(json.dumps(result, indent=2))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(result, indent=2))
    return 0 if result["written"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
