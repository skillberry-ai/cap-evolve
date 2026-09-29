"""merge — pairwise-merge ANY two live branch tips, gated like any other candidate (#586).

Why this exists. `merge_search.py` (#438) and `merge_rejects.py` (#560) both already merge
disjoint candidates via `integrate.py`/`funcmerge.py`, but each is scoped to how it FINDS its
two branches, not to the merge itself: `merge_search.py` only looks at THIS round's
screen-survivors staged under `$R/work/`, and `merge_rejects.py` only looks at candidates
`events.jsonl` recorded as a safe `"reject"` this run. Neither can merge two arbitrary tags —
e.g. an already-ACCEPTED candidate from an earlier iteration with a survivor from the current
round, or two accepted candidates from different points in the run's history — which is the
literal "two independently-evolving branches" #586 asks for.

This script is that generalization, and nothing else: given `--a TAG_A --b TAG_B`, it resolves
each tag to wherever its bytes currently live (`$R/work/<tag>` if it is still an uncommitted
branch, else `$R/candidates/<tag>` once `commit.py` has snapshotted it — see
`_resolve_branch_dir`), checks disjointness the same way `merge_search.changed_functions` does
(funcmerge.py's own per-function split — a real edit collision is refused, never force-merged),
and drives the SAME `integrate.py` engine via `merge_search._integrate` (generalized in this
same change to take explicit branch directories instead of assuming both live under `work/`).

It does NOT gate or commit anything, and it does NOT decide when to run — that stays the
driver's call, same as `merge_search.py`/`merge_rejects.py` today. A built merge lands at
`$R/work/merge_<a>_<b>`, an ordinary candidate directory `round.py --candidates merge_<a>_<b>`
gates through the exact same cascade as any hand-authored edit. On accept, commit it with
`commit.py --candidate merge_<a>_<b> --parents <a>,<b>` so `graph.jsonl` records BOTH ancestors
(`--parents` already exists — see `commit.py`/`core/cap_evolve/graph.py`, #434/#446) rather than
the single `parent` an ordinary edit gets.

Deferred (see the PR for #586): calling this automatically each round whenever 2+ branches are
live, and a policy for WHICH pairs among many live branches are worth trying (this script still
requires the caller to name the two tags).

    python merge.py --run-dir R --project P --a cand_7 --b old_accepted_3 --base seed \\
        --targets cand_7:1,2 --targets old_accepted_3:5,9 \\
        --canary-auto R/baseline.json --n 10 --conc 8 --floor 0.0333
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

import mechanisms
import merge_search

HERE = Path(__file__).resolve().parent


def _resolve_branch_dir(run_dir, tag: str) -> Path:
    """A tag's source directory wherever its bytes currently live.

    A "live branch tip" is either an uncommitted candidate still staged under `$R/work/`
    (what `merge_search.py`'s survivors are) or one `commit.py` has already snapshotted under
    `$R/candidates/` on ANY decision, accept or reject (what `merge_rejects.py`'s safe rejects
    are) — see `commit.py`'s `RunDir.snapshot` call, made regardless of `--decision`. Checking
    `work/` first means an in-progress edit to an already-committed tag (re-staged for a second
    look) is picked up over the stale committed snapshot.
    """
    work_dir = Path(run_dir.root) / "work" / tag
    if work_dir.is_dir():
        return work_dir
    cand_dir = run_dir.candidate_dir(tag)
    if cand_dir.is_dir():
        return cand_dir
    raise FileNotFoundError(
        f"tag {tag!r} not found under work/ or candidates/ for run {run_dir.root}")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="merge")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--project", required=True)
    ap.add_argument("--a", required=True, help="tag of the first live branch tip")
    ap.add_argument("--b", required=True, help="tag of the second live branch tip")
    ap.add_argument("--base", default="seed",
                    help="tag both branches are diffed against to find what each changed")
    ap.add_argument("--targets", action="append", default=[],
                    help="tag:comma,separated,task,ids — the tasks a branch targeted. "
                         "Repeatable. Falls back to mechanisms.jsonl's `tasks` field for rows "
                         "owned by that tag when omitted.")
    ap.add_argument("--file", default="tools/tools.py",
                    help="the Python file merged per function — see integrate.py --file")
    ap.add_argument("--prose", default="policy/policy.md")
    ap.add_argument("--canary-auto", default="",
                    help="path to a baseline per-task JSON — see merge_search.py --canary-auto")
    ap.add_argument("--canary", default="", help="explicit canary ids, if not using --canary-auto")
    ap.add_argument("--canary-floor", type=float, default=0.9)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--conc", type=int, default=8)
    ap.add_argument("--base-seed", type=int, default=0)
    ap.add_argument("--floor", type=float, default=0.0, help="measured null delta — see integrate.py --floor")
    ap.add_argument("--out-tag", default="", help="override the built candidate's tag")
    ap.add_argument("--json", dest="json_out", default="")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    import _bootstrap  # noqa: F401
    from cap_evolve import RunDir

    run_dir = RunDir.open(Path(args.run_dir))
    project = Path(args.project)
    work = run_dir.root / "work"
    work.mkdir(parents=True, exist_ok=True)

    try:
        base_dir = _resolve_branch_dir(run_dir, args.base)
        a_dir = _resolve_branch_dir(run_dir, args.a)
        b_dir = _resolve_branch_dir(run_dir, args.b)
    except FileNotFoundError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2

    base_file = base_dir / args.file
    a_file, b_file = a_dir / args.file, b_dir / args.file
    missing = [str(p) for p in (base_file, a_file, b_file) if not p.exists()]
    if missing:
        print(json.dumps({"error": f"file(s) not found: {missing}"}, indent=2))
        return 2

    base_src = base_file.read_text(encoding="utf-8")
    changed_a = merge_search.changed_functions(base_src, a_file.read_text(encoding="utf-8"))
    changed_b = merge_search.changed_functions(base_src, b_file.read_text(encoding="utf-8"))
    shared = changed_a & changed_b
    out = {
        "a": args.a, "b": args.b, "base": args.base,
        "changed_functions": {args.a: sorted(changed_a), args.b: sorted(changed_b)},
        "overlap": sorted(shared),
    }
    if shared:
        out["attempted"] = False
        out["reason"] = (f"{args.a} and {args.b} both touch {sorted(shared)} — a real edit "
                         "collision, not a mergeable pair of independent branches")
        print(json.dumps(out, indent=2))
        return 2

    explicit_targets: dict[str, list[str]] = {}
    for item in args.targets:
        tag, _, ids = item.partition(":")
        explicit_targets[tag.strip()] = [i.strip() for i in ids.split(",") if i.strip()]

    targets: dict[str, list[str]] = {}
    for tag in (args.a, args.b):
        t = explicit_targets.get(tag) or merge_search._mechanisms_targets(run_dir.root, tag)
        if not t:
            out["attempted"] = False
            out["reason"] = (f"no target task ids for {tag!r} (pass --targets or record them "
                             "in mechanisms.jsonl)")
            print(json.dumps(out, indent=2))
            return 2
        targets[tag] = t
    union_tasks = sorted({tid for ids in targets.values() for tid in ids})

    canary_auto = merge_search._canary_auto_file(args.canary_auto) if args.canary_auto else ""
    out_tag = args.out_tag or f"merge_{args.a}_{args.b}"
    result = merge_search._integrate(
        run_dir, project, work, base_dir, a_dir, b_dir, union_tasks,
        [i.strip() for i in args.canary.split(",") if i.strip()],
        canary_auto, args.canary_floor, args.n, args.conc, args.base_seed, args.floor,
        args.file, args.prose, out_tag)

    built = bool(result.get("out")) and (work / out_tag).is_dir() and "error" not in result
    out.update({"attempted": True, "tag": out_tag, "built": built, "targets": union_tasks,
               "result": result})

    if built:
        mechanisms.ledger(run_dir.root).parent.mkdir(parents=True, exist_ok=True)
        mechanisms_args = argparse.Namespace(
            run_dir=run_dir.root, owner=out_tag, status="proposed",
            mechanism=f"pairwise merge of live branches {args.a} + {args.b}",
            evidence=f"integrate.py accepted: {sorted(result.get('accepted', []))}; "
                     f"final_objective={result.get('final_objective')}",
            touches=sorted(changed_a) + sorted(changed_b),
            task=union_tasks, supersedes=[])
        # mechanisms.add() prints its own JSON on success; suppress it — this script has ONE
        # JSON document on stdout (see main()'s final print), same guard merge_search.py uses.
        with contextlib.redirect_stdout(io.StringIO()):
            mechanisms.add(mechanisms_args)
        out["next"] = (
            f"python round.py --run-dir {run_dir.root} --project {project} "
            f"--candidates {out_tag} --n-trials {args.n} --single-candidate-justification "
            "\"pairwise merge of two live branches per #586 — gating the merge alone\" — "
            "gates the merge through the SAME cascade as any candidate; on accept, commit "
            f"with `commit.py --candidate {out_tag} --parents {args.a},{args.b}` so "
            "graph.jsonl records BOTH ancestors, not a single parent")
    else:
        out["next"] = "merge was not built — see result.error"

    text = json.dumps(out, indent=2)
    print(text)
    if args.json_out:
        Path(args.json_out).write_text(text, encoding="utf-8")
    return 0 if built else 2


if __name__ == "__main__":
    sys.exit(main())
