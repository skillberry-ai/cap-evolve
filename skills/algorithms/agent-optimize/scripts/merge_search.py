"""merge_search — pairwise merge-as-graph-search over a round's disjoint-cluster survivors.

Why this exists. run_agentoptv3/run_agentoptv4 produced 3-6 narrow, single-issue candidates
per round, each individually gated on full val and rejected, and NEVER combined — no
integrate.py/funcmerge.py/merge_taskopt.py call appears in either run (#434, #438). The
merge machinery already exists and already works (see integrate.py/funcmerge.py's own
docstrings for the measured cases it was built to fix); the missing piece is simply DECIDING
which survivors are safe to try merging and DOING it, instead of leaving that to a driver
under time pressure who defaults to the cheapest step (another single candidate).

A round's "survivors" are candidates that got PAST screening (screen.py promote, or a
grow.py-provisional that ran out of growth rounds) without individually clearing the full-val
accept gate — see round.py/screen.py/grow.py. Two survivors are a MERGE CANDIDATE when the
functions/constants they changed, relative to the same base, are DISJOINT: `funcmerge.py`'s
own docstring is the reason overlapping edits are refused here rather than attempted — a
same-function collision is a genuine semantic disagreement funcmerge.py already declines to
auto-resolve, and offering it to a human via a merge conflict is not "graph search", it is
"ask a human what the graph search could not decide". Disjoint edits are exactly the
provably-safe case per-task-fanout.md already describes.

This script does NOT invent a new merge engine. Per pair it shells out to `integrate.py`
(one branch at a time, measured after each — see that file for why a one-shot N-way merge
does not compose) and forwards `--canary-auto` so the merge's objective is measured against
canaries drawn from the WHOLE suite, never just the neighbourhood of the two branches'
targets (per-task-fanout.md's "a canary set that only covers what you aimed at cannot catch
what you hit by accident" — restated here because a merge is exactly the moment two
neighbourhoods combine and the blast radius is not either one's alone).

It also does NOT gate anything. A successfully-built merge candidate is written to
`$R/work/merge_<a>_<b>` — an ordinary candidate directory, indistinguishable from any other
tag on disk — so `round.py --candidates merge_<a>_<b>,...` gates it through the EXACT SAME
cascade (null control, paired significance, no-regression veto) as a hand-authored edit. No
special-casing was added to round.py, deliberately: a merge is a candidate, not a new kind
of thing the gate has to know about.

Per-survivor target task ids come from `--targets tag:1,2,3` (repeatable) when given, else
from `mechanisms.jsonl`'s `tasks` field for rows owned by that tag (the ledger's existing
"who changed what, aimed at which tasks" record — see mechanisms.py). A survivor with
neither is skipped with a reason, never silently merged on an empty/whole-val objective.

Graph-DAG note (#435): this script currently reads survivor tags + a mechanisms ledger
directly, because no `graph.jsonl` exists yet on `main` to consume. Once #435 lands, the
survivor list and each one's `subset.rationale`/target ids should come from the DAG's
frontier nodes instead of `--survivors`/`--targets`/mechanisms.jsonl — the disjointness
check and the integrate.py call below do not change.

    python merge_search.py --run-dir R --project P --base BEST \\
        --survivors t7,t17,u33 --targets t7:1,2 --targets t17:5,9 \\
        --canary-auto R/baseline.json --n 10 --conc 8 --floor 0.0333
"""

from __future__ import annotations

import argparse
import contextlib
import io
import itertools
import json
import subprocess
import sys
from pathlib import Path

import funcmerge
import mechanisms

HERE = Path(__file__).resolve().parent


def _canary_auto_file(path: str) -> str:
    """Normalize a baseline JSON into the per-task DICT shape `integrate.py --canary-auto`
    reads (``{tid: {"rate": ...}}``, taskeval.py's own shape).

    The run's own ``$R/baseline.json`` (harness.baseline's output) is the file every run
    already has, but its ``per_task`` is a LIST of Score dicts (``harness.SplitResult``),
    one level down under ``"val"``. Reshaping it here — rather than teaching integrate.py a
    second per_task shape — keeps the merge engine itself unchanged.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    per = raw.get("per_task")
    if per is None and isinstance(raw.get("val"), dict):
        per = raw["val"].get("per_task")
    if isinstance(per, list):
        shaped = {str(row["task_id"]): {"rate": row.get("reward")}
                 for row in per if isinstance(row, dict) and row.get("task_id") is not None}
    elif isinstance(per, dict):
        return path  # already the shape integrate.py expects
    else:
        return path  # nothing recognizable — let integrate.py report the same error
    import tempfile
    fd, tmp = tempfile.mkstemp(suffix=".json", prefix="merge_search_canary_")
    Path(tmp).write_text(json.dumps({"per_task": shaped}), encoding="utf-8")
    return tmp


def changed_functions(base_src: str, variant_src: str) -> set[str]:
    """Names of functions/constants `variant_src` changed or added relative to `base_src`.

    Reuses funcmerge.blocks — the SAME per-function split integrate.py's own merge step
    runs on — so "disjoint" here means exactly what funcmerge.py would find non-conflicting,
    not a second, possibly-inconsistent notion of overlap.
    """
    _, base_fns = funcmerge.blocks(base_src)
    _, var_fns = funcmerge.blocks(variant_src)
    return {name for name, text in var_fns.items()
            if name not in base_fns or text != base_fns[name]}


def _mechanisms_targets(run_dir: Path, tag: str) -> list[str]:
    """Union of `tasks` from mechanisms.jsonl rows owned by `tag` (see mechanisms.py)."""
    path = Path(run_dir) / "mechanisms.jsonl"
    if not path.exists():
        return []
    ids: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        if row.get("owner") == tag:
            ids.update(str(t) for t in (row.get("tasks") or []))
    return sorted(ids)


def find_disjoint_pairs(base_src: str, survivor_srcs: dict[str, str]) -> dict:
    """Every survivor pair, split into disjoint (mergeable) vs overlapping (skipped).

    Returns {"changed": {tag: sorted[fn...]}, "disjoint_pairs": [[a, b], ...],
    "overlapping_pairs": [{"pair": [a, b], "shared": [fn...]}]}.
    """
    changed = {tag: changed_functions(base_src, src) for tag, src in survivor_srcs.items()}
    disjoint, overlapping = [], []
    for a, b in itertools.combinations(sorted(survivor_srcs), 2):
        shared = changed[a] & changed[b]
        if shared:
            overlapping.append({"pair": [a, b], "shared": sorted(shared)})
        else:
            disjoint.append([a, b])
    return {"changed": {t: sorted(v) for t, v in changed.items()},
            "disjoint_pairs": disjoint, "overlapping_pairs": overlapping}


def _integrate(run_dir: Path, project: Path, work: Path, base_dir: Path, a: str, b: str,
               tasks: list[str], canary: list[str], canary_auto: str, canary_floor: float,
               n: int, conc: int, base_seed: int, floor: float, file_: str, prose: str,
               out_tag: str) -> dict:
    json_out = work / f".{out_tag}_integrate.json"
    cmd = [sys.executable, str(HERE / "integrate.py"),
           "--base", str(base_dir), "--project", str(project),
           "--branches", str(work / a), str(work / b),
           "--out", str(work / out_tag), "--tasks", ",".join(tasks),
           "--n", str(n), "--conc", str(conc), "--base-seed", str(base_seed),
           "--floor", str(floor), "--file", file_, "--prose", prose,
           "--taskeval", str(HERE / "taskeval.py"), "--json", str(json_out)]
    if canary_auto:
        cmd += ["--canary-auto", canary_auto, "--canary-floor", str(canary_floor)]
    elif canary:
        cmd += ["--canary", ",".join(canary)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    # NOT json.loads(p.stdout): with --canary-auto, integrate.py prints the canary-selection
    # note as its OWN json.dumps call before the final result — two concatenated JSON
    # documents on one stream, which `json.loads` cannot parse as one object. `--json`
    # writes only the final result, so read that back instead.
    if json_out.exists():
        try:
            return json.loads(json_out.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return {"error": (p.stderr or p.stdout)[-1200:], "rc": p.returncode}


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="merge_search")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--project", required=True)
    ap.add_argument("--base", required=True, help="tag of the round's current parent")
    ap.add_argument("--survivors", required=True,
                    help="comma-separated tags under $R/work/ that passed screening but did "
                         "not individually clear the full-val accept gate")
    ap.add_argument("--targets", action="append", default=[],
                    help="tag:comma,separated,task,ids — the tasks this survivor targeted. "
                         "Repeatable. Falls back to mechanisms.jsonl's `tasks` field for rows "
                         "owned by that tag when omitted.")
    ap.add_argument("--file", default="tools/tools.py",
                    help="the Python file merged per function — see integrate.py --file")
    ap.add_argument("--prose", default="policy/policy.md")
    ap.add_argument("--canary-auto", default="",
                    help="path to a baseline per-task JSON. Canaries are drawn from the "
                         "WHOLE suite (per-task-fanout.md), not from the merged branches' "
                         "own neighbourhood — pass the run's baseline.json.")
    ap.add_argument("--canary", default="", help="explicit canary ids, if not using --canary-auto")
    ap.add_argument("--canary-floor", type=float, default=0.9)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--conc", type=int, default=8)
    ap.add_argument("--base-seed", type=int, default=0)
    ap.add_argument("--floor", type=float, default=0.0,
                    help="measured null delta — see integrate.py --floor")
    ap.add_argument("--json", dest="json_out", default="")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    run_dir = Path(args.run_dir)
    project = Path(args.project)
    work = run_dir / "work"
    survivors = [t.strip() for t in args.survivors.split(",") if t.strip()]
    canary_auto = _canary_auto_file(args.canary_auto) if args.canary_auto else ""

    explicit_targets: dict[str, list[str]] = {}
    for item in args.targets:
        tag, _, ids = item.partition(":")
        explicit_targets[tag.strip()] = [i.strip() for i in ids.split(",") if i.strip()]

    base_dir = work / args.base
    if not base_dir.is_dir():
        # The round's parent usually lives in candidates/, not work/ — only a branch
        # actively being merged gets a work/ copy. Fall back to the run's own record of
        # where that tag's snapshot is, rather than requiring the caller to pre-stage it.
        import _bootstrap  # noqa: F401
        from cap_evolve import RunDir
        base_dir = RunDir.open(run_dir).candidate_dir(args.base)
    base_file = base_dir / args.file
    if not base_file.exists():
        print(json.dumps({"error": f"base file not found: {base_file}"}, indent=2))
        return 2
    base_src = base_file.read_text(encoding="utf-8")

    survivor_srcs, missing = {}, []
    for tag in survivors:
        f = work / tag / args.file
        if not f.exists():
            missing.append(tag)
            continue
        survivor_srcs[tag] = f.read_text(encoding="utf-8")
    if missing:
        print(json.dumps({"error": f"survivor file(s) missing under {work}: {missing}"},
                         indent=2))
        return 2

    disjointness = find_disjoint_pairs(base_src, survivor_srcs)

    targets = {}
    skipped_no_targets = []
    for tag in survivors:
        t = explicit_targets.get(tag) or _mechanisms_targets(run_dir, tag)
        if t:
            targets[tag] = t
        else:
            skipped_no_targets.append(tag)

    merges = []
    ready_for_gate = []
    for a, b in disjointness["disjoint_pairs"]:
        if a in skipped_no_targets or b in skipped_no_targets:
            merges.append({"pair": [a, b], "attempted": False,
                          "reason": "no target task ids for at least one branch "
                                    "(pass --targets or record them in mechanisms.jsonl)"})
            continue
        union_tasks = sorted(set(targets[a]) | set(targets[b]))
        out_tag = f"merge_{a}_{b}"
        result = _integrate(run_dir, project, work, base_dir, a, b, union_tasks,
                            [i.strip() for i in args.canary.split(",") if i.strip()],
                            canary_auto, args.canary_floor, args.n, args.conc,
                            args.base_seed, args.floor, args.file, args.prose, out_tag)
        built = bool(result.get("out")) and (work / out_tag).is_dir() and "error" not in result
        merges.append({"pair": [a, b], "attempted": True, "tag": out_tag, "built": built,
                      "targets": union_tasks, "result": result})
        if built:
            ready_for_gate.append(out_tag)
            mechanisms.ledger(run_dir).parent.mkdir(parents=True, exist_ok=True)
            mechanisms_args = argparse.Namespace(
                run_dir=run_dir, owner=out_tag, status="proposed",
                mechanism=f"pairwise merge of disjoint-cluster survivors {a} + {b}",
                evidence=f"integrate.py accepted: {sorted(result.get('accepted', []))}; "
                         f"final_objective={result.get('final_objective')}",
                touches=sorted(disjointness["changed"].get(a, []))
                        + sorted(disjointness["changed"].get(b, [])),
                task=union_tasks, supersedes=[])
            # mechanisms.add() is written as a CLI subcommand and prints its own JSON on
            # success — fine standalone, but this script has ONE JSON document on stdout
            # (see main()'s final print) and mixing a second one in breaks any caller
            # parsing stdout as JSON. Suppress its print; the ledger write itself is
            # unaffected.
            with contextlib.redirect_stdout(io.StringIO()):
                mechanisms.add(mechanisms_args)

    out = {
        "base": args.base,
        "survivors": survivors,
        "changed_functions": disjointness["changed"],
        "disjoint_pairs": disjointness["disjoint_pairs"],
        "overlapping_pairs_skipped": disjointness["overlapping_pairs"],
        "skipped_no_targets": skipped_no_targets,
        "merges": merges,
        "ready_for_gate": ready_for_gate,
        "next": (f"python round.py --run-dir {run_dir} --project {project} "
                 f"--candidates {','.join(ready_for_gate)} --n-trials {args.n} "
                 "— gates each merge through the SAME cascade as any candidate"
                 if ready_for_gate else
                 "no merge candidate was built — see merges[].reason / merges[].result.error"),
    }
    text = json.dumps(out, indent=2)
    print(text)
    if args.json_out:
        Path(args.json_out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
