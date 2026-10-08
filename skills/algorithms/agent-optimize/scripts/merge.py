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

Within a round this is now automatic (#438): `round.py` calls `build_merge_dir` below on every
pair of disjoint screen-survivors, screens each merge, and gates a merge in place of its parents
only when it kept both parents' screened gains. This CLI remains for pairs `round.py` cannot see
— e.g. an accepted candidate from an earlier iteration with a current-round survivor.

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


def _capability_files(root: Path, ignore: set[str]) -> dict[str, Path]:
    """{relative path: file} under ``root``, skipping framework memory / caches."""
    out = {}
    for f in root.rglob("*"):
        rel = f.relative_to(root)
        if f.is_file() and not (set(rel.parts) & ignore):
            out[rel.as_posix()] = f
    return out


def _read(files: dict[str, Path], rel: str) -> bytes | None:
    return files[rel].read_bytes() if rel in files else None


def _changed_files(base_dir: Path, a_dir: Path, b_dir: Path):
    """(base_f, a_f, b_f, changed_a, changed_b): each branch's capability files and the
    relative paths it changed against ``base_dir``."""
    import _bootstrap  # noqa: F401
    from cap_evolve.harness import _SNAPSHOT_IGNORE

    # DIAGNOSIS.json is per-candidate optimizer metadata (#611), not capability bytes: each
    # sibling writes its own, so 3-way merging it would collide on EVERY pair. It is combined
    # from the parents in build_merge_dir instead.
    ignore = set(_SNAPSHOT_IGNORE) | {"PROCESS.md", "__pycache__", "DIAGNOSIS.json"}
    base_f, a_f, b_f = (_capability_files(d, ignore) for d in (base_dir, a_dir, b_dir))
    changed_a = {r for r in set(base_f) | set(a_f) if _read(base_f, r) != _read(a_f, r)}
    changed_b = {r for r in set(base_f) | set(b_f) if _read(base_f, r) != _read(b_f, r)}
    return base_f, a_f, b_f, changed_a, changed_b


def diff_contained(base_dir: Path, a_dir: Path, b_dir: Path) -> bool:
    """Is A's edit (vs ``base_dir``) a STRICT subset of B's? (#633)

    Literal containment, no judgement: every file A changed, B changed too, and 3-way merging
    A into B (``funcmerge.merge3``, the engine ``build_merge_dir`` uses) is a clean no-op —
    i.e. B already carries every one of A's hunks. Strict: B is not byte-identical to A.
    Conservative by construction: an overlapping-but-different hunk conflicts or changes B,
    so it reads as NOT contained and A is gated as before.
    """
    import funcmerge

    base_f, a_f, b_f, changed_a, changed_b = _changed_files(base_dir, a_dir, b_dir)
    if not changed_a or not changed_a <= changed_b:
        return False
    if all(_read(a_f, r) == _read(b_f, r) for r in changed_b):
        return False  # identical edits, not a strict subset
    for rel in changed_a:
        a_bytes, b_bytes = _read(a_f, rel), _read(b_f, rel)
        if a_bytes == b_bytes:
            continue
        if a_bytes is None or b_bytes is None or rel not in base_f:
            return False
        try:
            text, clean = funcmerge.merge3(base_f[rel].read_text(encoding="utf-8"),
                                           a_bytes.decode("utf-8"), b_bytes.decode("utf-8"))
        except UnicodeDecodeError:
            return False
        if not clean or text.encode("utf-8") != b_bytes:
            return False
    return True


def build_merge_dir(base_dir: Path, a_dir: Path, b_dir: Path, out_dir: Path) -> dict:
    """Build the pairwise merge of two branch tips WITHOUT measuring it (#438).

    The measurement-free half of this script's primitive, for ``round.py``'s automatic
    merge pass: every file is 3-way merged against ``base_dir`` (the round's parent) —
    a file only one branch changed is taken from that branch, a ``.py`` both changed goes
    through ``funcmerge.py`` (per-function, the same engine ``integrate.py`` uses), any
    other file both changed through ``git merge-file``. Any collision is refused, never
    forced: ``{"built": False, "conflicts": [...]}``. The merge is then judged by the SAME
    screen -> gate cascade as any candidate, which is what replaces ``integrate.py``'s own
    per-step taskeval measurement here (N+1 subset evals at ``--n`` trials each would
    cost more than the screen it feeds).
    """
    import shutil
    import subprocess
    import tempfile

    import funcmerge

    base_f, a_f, b_f, changed_a, changed_b = _changed_files(base_dir, a_dir, b_dir)
    plan: dict[str, bytes | None] = {}
    conflicts, merged_files = [], []
    for rel in sorted(changed_a | changed_b):
        a_bytes, b_bytes = _read(a_f, rel), _read(b_f, rel)
        if rel not in changed_b or a_bytes == b_bytes:
            plan[rel] = a_bytes
            continue
        if rel not in changed_a:
            plan[rel] = b_bytes
            continue
        if a_bytes is None or b_bytes is None or rel not in base_f:
            conflicts.append({"file": rel, "why": "added or deleted by both branches"})
            continue
        merged_files.append(rel)
        if rel.endswith(".py"):
            with tempfile.TemporaryDirectory() as td:
                out = Path(td) / "merged.py"
                p = subprocess.run(
                    [sys.executable, str(HERE / "funcmerge.py"), "--base", str(base_f[rel]),
                     "--out", str(out), "--inputs", str(a_f[rel]), str(b_f[rel]),
                     "--union-pure-insertions", "--json", str(Path(td) / "r.json")],
                    capture_output=True, text=True)
                if p.returncode == 0 and out.exists():
                    plan[rel] = out.read_bytes()
                    continue
                try:
                    rep = json.loads((Path(td) / "r.json").read_text(encoding="utf-8"))
                    why = rep.get("conflicts") or rep.get("error")
                except (OSError, ValueError):
                    why = (p.stderr or p.stdout)[-300:]
            conflicts.append({"file": rel, "why": f"funcmerge: {why}"})
            continue
        text, clean = funcmerge.merge3(base_f[rel].read_text(encoding="utf-8"),
                                       a_bytes.decode("utf-8"), b_bytes.decode("utf-8"))
        if clean:
            plan[rel] = text.encode("utf-8")
        else:
            conflicts.append({"file": rel, "why": "both branches edited the same lines"})
    result = {"changed": {"a": sorted(changed_a), "b": sorted(changed_b)},
              "three_way_merged": merged_files, "conflicts": conflicts,
              "built": not conflicts}
    if conflicts:
        return result
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(base_dir, out_dir, ignore=shutil.ignore_patterns("__pycache__"))
    for rel, data in plan.items():
        dst = out_dir / rel
        if data is None:
            dst.unlink(missing_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
    result["diagnosis_clusters"] = _write_merged_diagnosis(a_dir, b_dir, out_dir)
    return result


def _write_merged_diagnosis(a_dir: Path, b_dir: Path, out_dir: Path) -> list[str]:
    """The merge's DIAGNOSIS.json = both parents' diagnoses combined (#611).

    A merge targets exactly what its parents targeted, so its clusters are their clusters
    (tasks unioned per id) and its edits are both parents' edits — which is what commit.py's
    #611 precondition reads. The copied-in round parent's diagnosis is REMOVED, never kept:
    it describes a different candidate and would satisfy the precondition with the wrong
    clusters. Neither parent having one leaves no file, so the commit asks for a reason.
    """
    target = out_dir / "DIAGNOSIS.json"
    target.unlink(missing_ok=True)
    clusters: dict[str, dict] = {}
    edits: list = []
    for d in (a_dir, b_dir):
        try:
            diag = json.loads((d / "DIAGNOSIS.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(diag, dict):
            continue
        for c in diag.get("clusters") or []:
            if not (isinstance(c, dict) and c.get("id")):
                continue
            cur = clusters.setdefault(str(c["id"]), {**c, "tasks": []})
            cur["tasks"] = sorted({*cur["tasks"], *(str(t) for t in c.get("tasks") or [])})
        edits += [e for e in diag.get("edits") or [] if isinstance(e, dict)]
    if clusters:
        target.write_text(json.dumps({
            "candidate": out_dir.name,
            "headline": f"pairwise merge of {a_dir.name} + {b_dir.name}",
            "clusters": list(clusters.values()), "edits": edits}, indent=2), encoding="utf-8")
    return list(clusters)


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

    # #684 item 5: whole-tree GEPA mergeable-ness check (merge_search.is_mergeable), replacing
    # the single-file (--file only) changed_functions comparison this used to run — that older
    # check could not see a conflict in any OTHER capability file (e.g. --prose), and this is
    # the SAME check round.py's intra-round merge_stage now requires per #684 item 4, so a pair
    # judged mergeable here and inside one round mean the same thing.
    check = merge_search.is_mergeable(a_dir, b_dir, base_dir)
    out = {
        "a": args.a, "b": args.b, "base": args.base,
        "changed_a": check["changed_a"], "changed_b": check["changed_b"],
        "conflicts": check["conflicts"], "identical_overlaps": check["identical_overlaps"],
    }
    if not check["mergeable"]:
        out["attempted"] = False
        out["reason"] = (f"{args.a} and {args.b} both independently diverged from {args.base!r} "
                         f"on {check['conflicts']} — a real edit collision, not a mergeable "
                         "pair of independent branches")
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
            touches=sorted(check["changed_a"]) + sorted(check["changed_b"]),
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
