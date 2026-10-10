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


def is_mergeable(candidate_a: Path, candidate_b: Path, common_ancestor: Path,
                 md_blocks: bool | None = None) -> dict:
    """GEPA's mergeable-ness check (arXiv:2507.19457, Appendix D, Algorithms 3-4), adapted to
    this project's capability tree instead of GEPA's list-of-modules abstraction.

    "Module" here is this project's EXISTING merge granularity, reused rather than invented:
    every file under the capability path (``merge._changed_files``, the same scan
    ``merge.build_merge_dir``/``merge.diff_contained`` already use for whole-tree disjointness),
    with each ``.py`` file split further into per-function/constant blocks (``funcmerge.blocks``
    — the same split ``integrate.py``/``funcmerge.py`` merge on, and ``changed_functions``
    above uses for the single-file case). Two candidates are mergeable at ``common_ancestor``
    iff, for every module, AT MOST ONE of them independently diverged from the ancestor's
    version of that module.

    Edge case, documented per the issue that asked for this check: when BOTH candidates
    diverged on the same module but to byte-identical content, this is reported as mergeable
    (listed under ``identical_overlaps``, not ``conflicts``) rather than refused. GEPA's own
    Desirable() check (Algorithm 4) only tests "did i change M" vs "did j change M" and would
    refuse this case too, but two edits that are not actually different cannot be a real
    disagreement, and refusing them would reject work that cannot possibly conflict.

    ``md_blocks`` (ablation key ``merge.md_blocks``, default on, #709): ``.md``/``.txt`` files are
    split into heading-section blocks (``cap_evolve.mdblocks``) instead of being one whole-file
    module, so siblings editing different sections of one policy.md are not a false collision.
    Off = legacy whole-file verdict. ``None`` resolves via ``mdblocks.enabled()`` (env
    ``CAPEVOLVE_MD_BLOCKS=0`` turns it off; ``round.py`` passes the capevolve.yaml
    ``merge.md_blocks`` value). ``merge.build_merge_dir`` builds the same blocks, so a pair judged
    mergeable here is buildable. Block-disjoint is MECHANICAL mergeability, not semantic safety:
    the merged child still goes through screen/gate.
    """
    import merge as merge_mod
    import _bootstrap  # noqa: F401
    from cap_evolve import mdblocks

    md_blocks = mdblocks.enabled() if md_blocks is None else md_blocks

    base_f, a_f, b_f, changed_a, changed_b = merge_mod._changed_files(
        common_ancestor, candidate_a, candidate_b)
    both = sorted(changed_a & changed_b)
    conflicts: list[str] = []
    identical: list[str] = []
    for rel in both:
        a_bytes, b_bytes = merge_mod._read(a_f, rel), merge_mod._read(b_f, rel)
        if a_bytes == b_bytes:
            identical.append(rel)
            continue
        if md_blocks and rel.endswith((".md", ".txt")) and a_bytes is not None \
                and b_bytes is not None and rel in base_f:
            try:
                r = mdblocks.three_way(*(mdblocks.decode(x) for x in
                                         (base_f[rel].read_bytes(), a_bytes, b_bytes)))
            except UnicodeDecodeError:
                conflicts.append(rel)
                continue
            conflicts += [f"{rel}::{i}" for i in r["conflicts"]]
            identical += [f"{rel}::{i}" for i in r["identical"]]
            continue
        if not rel.endswith(".py") or a_bytes is None or b_bytes is None or rel not in base_f:
            conflicts.append(rel)  # whole-file module: both diverged, differently
            continue
        try:
            _, base_fns = funcmerge.blocks(base_f[rel].read_text(encoding="utf-8"))
            _, a_fns = funcmerge.blocks(a_bytes.decode("utf-8"))
            _, b_fns = funcmerge.blocks(b_bytes.decode("utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            conflicts.append(rel)
            continue
        for name in sorted(set(a_fns) | set(b_fns) | set(base_fns)):
            a_fn, b_fn, base_fn = a_fns.get(name), b_fns.get(name), base_fns.get(name)
            if a_fn != base_fn and b_fn != base_fn:         # both diverged on this sub-module
                (identical if a_fn == b_fn else conflicts).append(f"{rel}::{name}")
    return {
        "mergeable": not conflicts,
        "conflicts": conflicts,
        "identical_overlaps": identical,
        "changed_a": sorted(changed_a),
        "changed_b": sorted(changed_b),
        "both_changed_files": both,
    }


def build_merge(candidate_a: Path, candidate_b: Path, common_ancestor: Path,
                out_dir: Path) -> dict:
    """Construct the merge of two candidates found mergeable by ``is_mergeable`` above.

    Per module: a module only one candidate changed is taken from that candidate; a module
    neither changed keeps the ancestor's version unchanged; a module both changed (which
    ``is_mergeable`` only allows through when the changes are identical) resolves to either
    one, since they are the same bytes.

    This does NOT reimplement that construction — it delegates to ``merge.build_merge_dir``,
    the merge engine ``round.py``'s cross-round merge (``merge.py``) and intra-round merge
    (this module's own ``find_disjoint_pairs``/``round.merge_stage``) already share. That
    engine is strictly more capable than the paragraph above describes (it 3-way-merges a
    both-changed module at line/function granularity via ``funcmerge``/``git merge-file``
    rather than requiring byte-identical content), so a pair ``is_mergeable`` rejects can,
    rarely, still build cleanly here — intentional: the GEPA check above is the conservative
    gate that decides whether a merge is WORTH ATTEMPTING, not the thing that builds it.
    """
    import merge as merge_mod

    return merge_mod.build_merge_dir(common_ancestor, candidate_a, candidate_b, out_dir)


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


def _integrate(run_dir: Path, project: Path, work: Path, base_dir: Path, a_dir: Path, b_dir: Path,
               tasks: list[str], canary: list[str], canary_auto: str, canary_floor: float,
               n: int, conc: int, base_seed: int, floor: float, file_: str, prose: str,
               out_tag: str) -> dict:
    """Merge two branches, given their SOURCE DIRECTORIES directly rather than tags implicitly
    rooted under ``work/`` — the generalization ``merge.py`` (#586) needs to merge a branch
    that lives under ``candidates/`` (already committed) with one still under ``work/``
    (an uncommitted survivor), which is exactly what "any two live branch tips" means.
    ``merge_search.py``'s own call site below is unaffected: it simply passes ``work / a``.
    """
    json_out = work / f".{out_tag}_integrate.json"
    cmd = [sys.executable, str(HERE / "integrate.py"),
           "--base", str(base_dir), "--project", str(project),
           "--branches", str(a_dir), str(b_dir),
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


def check_merge_compliance(run_dir) -> dict | None:
    """Audit signal, not an enforcement: did this run merge disjoint-cluster accepted
    candidates before finalizing?

    SKILL.md requires the optimizer to run this script on its accepted candidates before
    any end-of-run measurement, whenever 2+ of them target disjoint task clusters — the
    exact shape this script exists to combine (module docstring above). Nothing in the
    framework can force the agent to actually do that (host.py owns no algorithm
    decisions), so this is the same kind of code-level compliance signal
    ``round.py``'s ``agent_optimize_compliance`` event already logs for the screen
    ladder: it never blocks, it only makes the omission visible in ``events.jsonl`` and
    the dashboard's activity log.

    Reads ``graph.jsonl`` for ``status == "accepted"`` nodes and each one's target task
    ids — its own ``cluster_ids`` if a caller has populated that field, else the same
    ``mechanisms.jsonl`` fallback this script's own ``main()`` uses to pick merge targets
    (`_mechanisms_targets`). Two or more accepted candidates whose target sets are
    pairwise DISJOINT, with no ``edit_kind == "merge"`` node anywhere in the graph, means
    the run's "best" is whichever single cluster's fix happened to score highest, never a
    combination of them.

    Returns ``None`` when there is nothing to flag (fewer than 2 accepted candidates with
    known targets, none of their target sets are disjoint, or a merge was already
    attempted this run), else a dict of fields for ``RunDir.log_event``.
    """
    import _bootstrap  # noqa: F401
    from cap_evolve import graph as graph_mod

    nodes = graph_mod.read_nodes(run_dir)
    accepted = [n for n in nodes if n.get("status") == "accepted"]

    targets: dict[str, list[str]] = {}
    for n in accepted:
        tag = n.get("id")
        if not tag:
            continue
        ids = n.get("cluster_ids") or _mechanisms_targets(run_dir.root, tag)
        if ids:
            targets[tag] = sorted(set(ids))
    if len(targets) < 2:
        return None

    disjoint_pairs = [[a, b] for a, b in itertools.combinations(sorted(targets), 2)
                      if not (set(targets[a]) & set(targets[b]))]
    if not disjoint_pairs:
        return None

    if any(n.get("edit_kind") == "merge" for n in nodes):
        return None  # a merge was attempted this run — nothing to flag

    return {
        "reason": "merge_skipped_with_multiple_clusters",
        "accepted_candidates": sorted(targets),
        "targets": targets,
        "disjoint_pairs": disjoint_pairs,
    }


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
    ap.add_argument("--nway", action="store_true",
                    help="#710: fold ALL survivors by merge-base with an interaction score and a "
                         "probe plan (merge_n.py) instead of pairwise integrate.py. Prints the "
                         "plan; builds $R/work/merge_<tags>. Ablation smart_merge off => ignored.")
    return ap


def _nway(args, run_dir: Path, survivors: list[str]) -> int:
    import _bootstrap  # noqa: F401
    import merge_n
    from cap_evolve import RunDir
    from cap_evolve.candidate_graph import CandidateGraph
    from cap_evolve.specfile import spec_for_run

    rd = RunDir.open(run_dir)
    if not merge_n.enabled(spec_for_run(rd, Path(args.project))):
        print("smart_merge is off; use the pairwise path (omit --nway)", file=sys.stderr)
        return 2
    work = run_dir / "work"
    dir_of = lambda t: work / t if (work / t).is_dir() else rd.candidate_dir(t)  # noqa: E731
    graph = CandidateGraph.load(rd)
    for t in survivors:  # survivors are not in the graph yet: attach them to --base
        if t not in graph:
            graph._nodes[t] = {"id": t, "parents": [args.base]}
    tt = {t: _mechanisms_targets(run_dir, t) for t in survivors}
    wins = merge_n.wins_from_run(rd, survivors, args.base)
    out_tag = "merge_" + "_".join(survivors)
    for t, ids in tt.items():
        if not ids:
            print(f"merge_search WARNING: no mechanisms.jsonl tasks for {t}", file=sys.stderr)
    res = merge_n.plan(survivors, dir_of, graph, touched_tasks=tt, wins=wins or {},
                       all_tasks=rd.read_splits().ids("val"),          # val only, never test
                       canaries=[c.strip() for c in args.canary.split(",") if c.strip()] or None,
                       out_dir=work / out_tag, run_dir=rd)
    res["node"] = merge_n.node_record(res, out_tag)
    print(json.dumps(res, indent=2, default=sorted))
    return 0 if res["built"] else 1


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    run_dir = Path(args.run_dir)
    project = Path(args.project)
    work = run_dir / "work"
    survivors = [t.strip() for t in args.survivors.split(",") if t.strip()]
    if args.nway:
        return _nway(args, run_dir, survivors)
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
        result = _integrate(run_dir, project, work, base_dir, work / a, work / b, union_tasks,
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
        # round.py refuses --candidates below its MIN_SIBLINGS (3) without a recorded reason
        # (see round.py's SingleCandidateUnjustified). A merged survivor gated alone is exactly
        # SKILL.md's documented screen-then-merge case, not an omission, so this command
        # supplies that justification itself rather than printing a command the driver would
        # have to edit before it runs.
        "next": (f"python round.py --run-dir {run_dir} --project {project} "
                 f"--candidates {','.join(ready_for_gate)} --n-trials {args.n}"
                 + (" --single-candidate-justification "
                    "\"screen-then-merge: gating the merged survivor(s) alone per SKILL.md's "
                    "bucket A\"" if len(ready_for_gate) < 3 else "")
                 + " — gates each merge through the SAME cascade as any candidate"
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
